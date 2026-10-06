"""Train and evaluate the forecasting models; write models/ and FORECASTS.md.

Run weekly by .github/workflows/forecast.yml. Each model is first scored on a
held-out recent period it never saw (weather: last 365 days, dengue: last 6
weeks) against simple baselines, then refit on all data for production.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from model import (HORIZONS, MODELS, ROOT, WEATHER_TARGETS, dengue_columns,
                   dengue_features, load, weather_columns, weather_features)

SL_TZ = timezone(timedelta(hours=5, minutes=30))
WEATHER_TEST_DAYS = 365
DENGUE_TEST_WEEKS = 6
LABELS = {"temp_max_c": "Max temperature (°C)", "temp_min_c": "Min temperature (°C)",
          "precipitation_mm": "Rainfall (mm)"}


def regressor(poisson):
    return HistGradientBoostingRegressor(
        loss="poisson" if poisson else "squared_error", max_iter=300, learning_rate=0.05,
        max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0,
        categorical_features="from_dtype", random_state=0)


def growth_regressor():
    """Dengue: predicts log(next week / this week), heavily regularised, so with
    little data it stays close to "same as this week"."""
    return HistGradientBoostingRegressor(
        max_iter=100, learning_rate=0.05, max_leaf_nodes=7, min_samples_leaf=40,
        l2_regularization=5.0, categorical_features="from_dtype", random_state=0)


def growth_target(rows):
    return np.log1p(rows.y_cases_next) - np.log1p(rows.cases_lag0)


def from_growth(rows, growth):
    return np.clip(np.expm1(np.log1p(rows.cases_lag0) + growth), 0, None)


def mae(a, b):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def train_weather(weather):
    feats = weather_features(weather)
    last = feats.date.max()
    cut = last - pd.Timedelta(days=WEATHER_TEST_DAYS)
    results, bundles = [], {}
    for t in WEATHER_TARGETS:
        for h in HORIZONS:
            cols, y = weather_columns(h), f"y_{t}_h{h}"
            rows = feats.dropna(subset=[c for c in cols if c != "city"] + [y])
            train = rows[rows.date + pd.Timedelta(days=h) <= cut]
            test = rows[rows.date > cut]
            m = regressor(t == "precipitation_mm").fit(train[cols], train[y])
            pred = np.clip(m.predict(test[cols]), 0 if t == "precipitation_mm" else None, None)
            clim = (train.assign(month=(train.date + pd.Timedelta(days=h)).dt.month)
                    .groupby(["city", "month"], observed=True)[y].mean())
            clim_pred = clim.reindex(pd.MultiIndex.from_arrays(
                [test.city, (test.date + pd.Timedelta(days=h)).dt.month])).to_numpy()
            r = {"target": t, "horizon_days": h, "test_rows": len(test),
                 "model_mae": mae(test[y], pred),
                 "persistence_mae": mae(test[y], test[f"{t}_lag0"]),
                 "climatology_mae": mae(test[y], clim_pred)}
            r["skill_vs_best_baseline"] = 1 - r["model_mae"] / min(r["persistence_mae"], r["climatology_mae"])
            results.append(r)
            final = regressor(t == "precipitation_mm").fit(rows[cols], rows[y])
            bundles[f"weather_{t}_h{h}"] = {"model": final, "columns": cols,
                                            "categories": list(feats.city.cat.categories)}
            print(f"weather {t} h{h}: MAE {r['model_mae']:.2f} vs persistence "
                  f"{r['persistence_mae']:.2f}, climatology {r['climatology_mae']:.2f}", file=sys.stderr)
    info = {"rows": int(len(feats)), "from": str(feats.date.min().date()), "to": str(last.date()),
            "test_from": str((cut + pd.Timedelta(days=1)).date())}
    return results, bundles, info


def train_dengue(dengue, weather):
    feats = dengue_features(dengue, weather)
    cols = dengue_columns()
    rows = feats.dropna(subset=["cases_lag0", "y_cases_next"])
    weeks = rows[["year", "week"]].drop_duplicates().sort_values(["year", "week"])
    test_weeks = set(map(tuple, weeks.tail(DENGUE_TEST_WEEKS).to_numpy()))
    is_test = rows[["year", "week"]].apply(tuple, axis=1).isin(test_weeks)
    train, test = rows[~is_test], rows[is_test]
    m = growth_regressor().fit(train[cols], growth_target(train))
    pred = from_growth(test, m.predict(test[cols]))
    r = {"target": "cases_next_week", "test_rows": len(test),
         "model_mae": mae(test.y_cases_next, pred),
         "persistence_mae": mae(test.y_cases_next, test.cases_lag0)}
    r["skill_vs_best_baseline"] = 1 - r["model_mae"] / r["persistence_mae"]
    # Only publish model forecasts if the model beat the baseline on held-out weeks.
    r["published_method"] = "model" if r["skill_vs_best_baseline"] > 0 else "persistence"
    print(f"dengue: MAE {r['model_mae']:.1f} vs persistence {r['persistence_mae']:.1f} "
          f"-> publishing {r['published_method']}", file=sys.stderr)
    final = growth_regressor().fit(rows[cols], growth_target(rows))
    bundle = {"model": final, "columns": cols, "categories": list(feats.district.cat.categories),
              "method": r["published_method"]}
    info = {"rows": int(len(rows)), "weeks": int(len(weeks)),
            "test_weeks": sorted(f"{y}-W{w:02d}" for y, w in test_weeks)}
    return r, bundle, info


def live_accuracy(weather, days=30):
    """MAE of the forecasts actually published, over the last `days` days."""
    path = os.path.join(ROOT, "data", "forecasts_weather.csv")
    if not os.path.exists(path):
        return []
    fc = pd.read_csv(path, parse_dates=["target_date"])
    joined = fc.merge(weather, left_on=["target_date", "city"], right_on=["date", "city"],
                      suffixes=("_pred", ""))
    joined = joined[joined.target_date > joined.target_date.max() - pd.Timedelta(days=days)]
    out = []
    for h, g in joined.groupby("horizon_days"):
        for t in WEATHER_TARGETS:
            out.append({"target": t, "horizon_days": int(h), "forecasts": len(g),
                        "mae": mae(g[t], g[f"{t}_pred"])})
    return out


def pct(x):
    return f"{x:+.0%}"


def write_report(now, w_results, w_info, d_result, d_info, live):
    lines = [
        "# Forecasts", "",
        f"Models retrained {now:%Y-%m-%d %H:%M} (Sri Lanka time) by the weekly forecast "
        "workflow. Forecasts are in [`data/forecasts_weather.csv`](data/forecasts_weather.csv) "
        "and [`data/forecasts_dengue.csv`](data/forecasts_dengue.csv).", "",
        "Each model is scored on recent data it was **not** trained on and compared with two "
        "baselines: *persistence* (tomorrow = today) and *climatology* (the usual value for "
        "that city and month). **Skill** is the error reduction against the better baseline; "
        "negative skill means the model is worse than the baseline.", "",
        "## Weather (26 cities)", "",
        f"Trained on {w_info['rows']:,} city-days ({w_info['from']} to {w_info['to']}); "
        f"tested on {w_info['test_from']} to {w_info['to']}.", "",
        "| Target | Days ahead | Model MAE | Persistence MAE | Climatology MAE | Skill |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in w_results:
        lines.append(f"| {LABELS[r['target']]} | {r['horizon_days']} | {r['model_mae']:.2f} | "
                     f"{r['persistence_mae']:.2f} | {r['climatology_mae']:.2f} | "
                     f"{pct(r['skill_vs_best_baseline'])} |")
    lines += [
        "", "## Dengue (26 districts, next week's cases)", "",
        f"Trained on {d_info['rows']:,} district-weeks ({d_info['weeks']} weeks); tested on "
        f"{', '.join(d_info['test_weeks'])}. The model predicts the week-on-week growth "
        "rate. Few weeks of history exist so far, so it is experimental: published "
        "forecasts use the model only while it beats *persistence* (next week = this "
        f"week) on held-out weeks. **Currently publishing: {d_result['published_method']}.**", "",
        "| Target | Model MAE | Persistence MAE | Skill |", "|---|---:|---:|---:|",
        f"| Cases next week (per district) | {d_result['model_mae']:.1f} | "
        f"{d_result['persistence_mae']:.1f} | {pct(d_result['skill_vs_best_baseline'])} |",
    ]
    if live:
        lines += ["", "## Live accuracy (published forecasts, last 30 days)", "",
                  "| Target | Days ahead | Forecasts | MAE |", "|---|---:|---:|---:|"]
        for r in live:
            lines.append(f"| {LABELS[r['target']]} | {r['horizon_days']} | {r['forecasts']} | {r['mae']:.2f} |")
    lines += ["", "MAE = mean absolute error, in the target's units (°C, mm, cases).", ""]
    with open(os.path.join(ROOT, "FORECASTS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main():
    now = datetime.now(SL_TZ)
    weather = load("weather.csv", ("date",))
    dengue = load("dengue.csv", ("week_start",))

    w_results, bundles, w_info = train_weather(weather)
    d_result, d_bundle, d_info = train_dengue(dengue, weather)
    bundles["dengue_cases_next"] = d_bundle

    os.makedirs(MODELS, exist_ok=True)
    for name, bundle in bundles.items():
        joblib.dump(bundle, os.path.join(MODELS, f"{name}.joblib"), compress=3)
    live = live_accuracy(weather)
    with open(os.path.join(MODELS, "metrics.json"), "w") as fh:
        json.dump({"trained_at": now.strftime("%Y-%m-%dT%H:%M%z"), "weather": w_results,
                   "weather_data": w_info, "dengue": d_result, "dengue_data": d_info,
                   "live": live}, fh, indent=2)
    write_report(now, w_results, w_info, d_result, d_info, live)
    return 0


if __name__ == "__main__":
    sys.exit(main())
