"""Publish forecasts from the trained models.

Weather: for each city, the next two days after the latest complete day in
data/weather.csv. Dengue: next week's cases per district after the latest
report. Appends to data/forecasts_weather.csv and data/forecasts_dengue.csv;
a forecast already published for the same target is never rewritten.
"""

import os
import sys

import joblib
import numpy as np
import pandas as pd

from model import (DATA, HORIZONS, MODELS, WEATHER_TARGETS, dengue_features, load,
                   weather_features)

WEATHER_FIELDS = ["target_date", "city", "horizon_days", "based_on_date",
                  *WEATHER_TARGETS]
DENGUE_FIELDS = ["year", "week", "week_start", "district", "cases_pred", "method", "based_on_week"]


def bundle(name):
    return joblib.load(os.path.join(MODELS, f"{name}.joblib"))


def append_new(filename, fields, rows, key):
    path = os.path.join(DATA, filename)
    new = pd.DataFrame(rows, columns=fields)
    if os.path.exists(path):
        old = pd.read_csv(path, dtype=str)
        seen = set(map(tuple, old[key].to_numpy()))
        new = new[[tuple(map(str, k)) not in seen for k in new[key].to_numpy()]]
    if len(new):
        new.to_csv(path, mode="a", header=not os.path.exists(path), index=False)
    return len(new)


def predict_weather(weather):
    first = bundle(f"weather_{WEATHER_TARGETS[0]}_h{HORIZONS[0]}")
    feats = weather_features(weather, first["categories"])
    latest = feats.sort_values("date").groupby("city", observed=True).tail(1)
    rows = []
    for h in HORIZONS:
        preds = {}
        for t in WEATHER_TARGETS:
            b = bundle(f"weather_{t}_h{h}")
            usable = latest.dropna(subset=[c for c in b["columns"] if c != "city"])
            p = b["model"].predict(usable[b["columns"]])
            preds[t] = pd.Series(np.clip(p, 0, None) if t == "precipitation_mm" else p,
                                 index=usable.index)
        for i, r in latest.iterrows():
            if all(i in preds[t].index for t in WEATHER_TARGETS):
                rows.append({"target_date": (r.date + pd.Timedelta(days=h)).date().isoformat(),
                             "city": r.city, "horizon_days": h,
                             "based_on_date": r.date.date().isoformat(),
                             **{t: round(float(preds[t][i]), 1) for t in WEATHER_TARGETS}})
    return append_new("forecasts_weather.csv", WEATHER_FIELDS, rows,
                      ["target_date", "city", "horizon_days"])


def predict_dengue(dengue, weather):
    b = bundle("dengue_cases_next")
    feats = dengue_features(dengue, weather, b["categories"])
    latest = feats.sort_values(["year", "week"]).groupby("district", observed=True).tail(1)
    latest = latest.dropna(subset=["cases_lag0"])
    if b["method"] == "model":
        growth = b["model"].predict(latest[b["columns"]])
        preds = np.clip(np.expm1(np.log1p(latest.cases_lag0) + growth), 0, None)
    else:  # the model did not beat the baseline on held-out weeks
        preds = latest.cases_lag0.to_numpy()
    rows = []
    for (_, r), p in zip(latest.iterrows(), preds):
        start = r.week_start + pd.Timedelta(days=7)
        iso = start.isocalendar()
        rows.append({"year": iso.year, "week": iso.week, "week_start": start.date().isoformat(),
                     "district": r.district, "cases_pred": int(round(p)), "method": b["method"],
                     "based_on_week": f"{r.year}-W{r.week:02d}"})
    return append_new("forecasts_dengue.csv", DENGUE_FIELDS, rows, ["year", "week", "district"])


def main():
    weather = load("weather.csv", ("date",))
    dengue = load("dengue.csv", ("week_start",))
    w = predict_weather(weather)
    d = predict_dengue(dengue, weather)
    print(f"Forecasts: {w} weather row(s), {d} dengue row(s) added", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
