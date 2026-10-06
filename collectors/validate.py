"""Validate data/ before it is committed and write STATUS.md.

Whole-file checks: the CSV parses, the header matches the committed version,
and keys are unique and non-blank. Row checks (only on rows that are new or
changed compared with the last commit, so history never breaks the build):
values in plausible ranges, cross-field rules, and no implausible jumps from
the previous value. A file that fails is restored to its committed version,
so bad data is never committed, and the script exits 1.

STATUS.md lists every dataset with its row count, latest data and whether it
is fresh, so a source that silently stopped updating is visible.
"""

import csv
import io
import os
import subprocess
import sys
from datetime import date

from common import DATA_DIR, REPO_ROOT, log, sl_today

R = lambda lo, hi: (lo, hi)  # noqa: E731  (plausible value range)

# file -> rules. fresh = (column holding a date, max age in days, expected cadence);
# blank_key = key columns that may legitimately be blank.
RULES = {
    "weather.csv": dict(
        key=["date", "city"], fresh=("date", 3, "daily"),
        ranges={"temp_max_c": R(5, 45), "temp_min_c": R(0, 40), "precipitation_mm": R(0, 700),
                "wind_speed_max_kmh": R(0, 250), "humidity_mean_pct": R(0, 100)},
        rules=[("temp_min_c <= temp_max_c", lambda r: f(r, "temp_min_c") <= f(r, "temp_max_c"))]),
    "solar.csv": dict(
        key=["date", "city"], fresh=("date", 3, "daily"),
        ranges={"radiation_kwh_m2": R(0, 12), "sunshine_hours": R(0, 14),
                "daylight_hours": R(11, 13.5), "uv_index_max": R(0, 20)},
        rules=[("sunshine_hours <= daylight_hours",
                lambda r: f(r, "sunshine_hours") <= f(r, "daylight_hours") + 0.01)]),
    "exchange_rates.csv": dict(
        key=["date", "currency"], fresh=("date", 3, "daily"),
        ranges={"lkr_per_unit": R(0.01, 5000)}, jump=("currency", "lkr_per_unit", 0.15)),
    "river_discharge.csv": dict(
        key=["date", "river"], fresh=("date", 3, "daily"),
        ranges={"discharge_m3s": R(0, 20000)}),
    "weather_snapshots.csv": dict(
        key=["time", "city"], fresh=("time", 1, "every 4 h"),
        ranges={"temp_c": R(5, 45), "feels_like_c": R(0, 60), "humidity_pct": R(0, 100),
                "precipitation_mm": R(0, 200), "cloud_cover_pct": R(0, 100),
                "wind_speed_kmh": R(0, 250), "wind_direction_deg": R(0, 360), "uv_index": R(0, 20)}),
    "air_quality.csv": dict(
        key=["time", "city"], fresh=("time", 1, "every 4 h"),
        ranges={"us_aqi": R(0, 500), "pm2_5": R(0, 1000), "pm10": R(0, 2000),
                "carbon_monoxide": R(0, 50000), "nitrogen_dioxide": R(0, 2000),
                "sulphur_dioxide": R(0, 2000), "ozone": R(0, 1000)}),
    "marine.csv": dict(
        key=["time", "location"], fresh=("time", 1, "every 4 h"),
        ranges={"wave_height_m": R(0, 20), "wave_period_s": R(0, 30), "wave_direction_deg": R(0, 360),
                "swell_wave_height_m": R(0, 20), "sea_surface_temp_c": R(20, 36)}),
    "earthquakes.csv": dict(
        key=["id"], fresh=("time_utc", None, "when events occur"),
        ranges={"magnitude": R(0, 10), "depth_km": R(-10, 800),
                "latitude": R(-2, 14), "longitude": R(72, 90)}),
    "dengue.csv": dict(
        # NDCU publishes each week's report about three weeks after it ends.
        key=["year", "week", "district"], fresh=("week_end", 35, "weekly"),
        ranges={"week": R(1, 53), "cases": R(0, 20000), "cumulative_cases": R(0, 1000000)},
        rules=[("cases <= cumulative_cases", lambda r: f(r, "cases") <= f(r, "cumulative_cases"))]),
    "fuel_prices.csv": dict(
        key=["date", "effective_time", "product_code"], blank_key=["effective_time"],
        fresh=("date", None, "on price changes"),
        ranges={"price_lkr_per_litre": R(1, 5000)}),
    "economy_indicators.csv": dict(
        key=["year", "indicator_id"], fresh=("year", None, "annual"), ranges={}),
    "cbsl_rates.csv": dict(
        key=["date"], fresh=("date", 5, "weekdays"),
        ranges={"ccpi_inflation_pct": R(-30, 100), "overnight_policy_rate_pct": R(0, 50),
                "usd_tt_buy": R(50, 2000), "usd_tt_sell": R(50, 2000)},
        rules=[("usd_tt_buy <= usd_tt_sell", lambda r: f(r, "usd_tt_buy") <= f(r, "usd_tt_sell"))],
        jump=(None, "usd_tt_buy", 0.10)),
    "tourism.csv": dict(
        key=["year", "month"], fresh=("as_of", 21, "weekly reports"),
        ranges={"month": R(1, 12), "arrivals": R(0, 1000000)}),
    "forecasts_weather.csv": dict(
        key=["target_date", "city", "horizon_days"], fresh=("based_on_date", 3, "daily"),
        ranges={"horizon_days": R(1, 7), "temp_max_c": R(5, 45), "temp_min_c": R(0, 40),
                "precipitation_mm": R(0, 700)}),
    "forecasts_dengue.csv": dict(
        key=["year", "week", "district"], fresh=("week_start", 42, "weekly"),
        ranges={"week": R(1, 53), "cases_pred": R(0, 20000)}),
    "cse_market.csv": dict(
        key=["date"], fresh=("date", 7, "trading days"),
        ranges={"aspi": R(1000, 100000), "sp_sl20": R(500, 50000), "trades": R(1, 10000000)},
        jump=(None, "aspi", 0.15)),
}


def f(row, col):
    return float(row[col])


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def read_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    return reader.fieldnames or [], list(reader)


def committed(filename):
    """(header, rows) of the file at HEAD, or None if it is not committed yet."""
    res = git("show", f"HEAD:data/{filename}")
    return read_csv(res.stdout) if res.returncode == 0 else None


def check_file(filename, rules):
    """Return a list of error strings for data/<filename>."""
    with open(os.path.join(DATA_DIR, filename), newline="", encoding="utf-8") as fh:
        header, rows = read_csv(fh.read())
    old = committed(filename)
    errors = []

    if old and old[0] != header:
        errors.append(f"header changed from {old[0]} to {header}")
    missing = [k for k in rules["key"] if k not in header]
    if missing:
        return errors + [f"key column(s) {missing} missing"]

    seen = set()
    for n, r in enumerate(rows, 2):
        if None in r or None in r.values():
            errors.append(f"line {n}: wrong number of fields")
            continue
        key = tuple(r[k] for k in rules["key"])
        if any(r[k] == "" for k in rules["key"] if k not in rules.get("blank_key", [])):
            errors.append(f"line {n}: blank key {key}")
        if key in seen:
            errors.append(f"line {n}: duplicate key {key}")
        seen.add(key)

    old_rows = old[1] if old else []
    old_set = {tuple(r.items()) for r in old_rows}
    new_rows = [r for r in rows if None not in r and tuple(r.items()) not in old_set]

    for r in new_rows:
        where = "/".join(r[k] for k in rules["key"])
        for col, (lo, hi) in rules.get("ranges", {}).items():
            value = r.get(col, "")
            if value == "":
                continue
            try:
                x = float(value)
            except ValueError:
                errors.append(f"{where}: {col}={value!r} is not a number")
                continue
            if not lo <= x <= hi:
                errors.append(f"{where}: {col}={x} outside {lo}..{hi}")
        for name, rule in rules.get("rules", []):
            try:
                ok = rule(r)
            except ValueError:
                continue  # blank or non-numeric; reported by the range check
            if not ok:
                errors.append(f"{where}: fails {name}")

    if "jump" in rules and old_rows:
        group, col, limit = rules["jump"]
        order = rules["key"][0]
        for r in new_rows:
            prev = [o for o in old_rows if (group is None or o[group] == r[group])
                    and o[order] < r[order] and o[col] not in ("", None)]
            if not prev or r[col] == "":
                continue
            before = float(max(prev, key=lambda o: o[order])[col])
            change = abs(float(r[col]) / before - 1) if before else 0
            if change > limit:
                errors.append(f"{r[order]}: {col} jumped {change:.0%} "
                              f"({before} -> {r[col]}), limit {limit:.0%}")
    return errors


def restore(filename):
    """Put data/<filename> back to its committed state (or remove a new file)."""
    if committed(filename) is not None:
        git("checkout", "--", f"data/{filename}")
    else:
        os.remove(os.path.join(DATA_DIR, filename))


def latest(filename, column):
    with open(os.path.join(DATA_DIR, filename), newline="", encoding="utf-8") as fh:
        values = [r[column] for r in csv.DictReader(fh) if r.get(column)]
    return len(values), max(values) if values else ""


def write_status(rejected):
    today = sl_today()
    lines = ["# Data status", "",
             "Updated automatically by the data workflow after validation.", "",
             "| Dataset | Rows | Latest data | Updates | Status |",
             "|---|---:|---|---|---|"]
    stale = []
    for filename, rules in RULES.items():
        if not os.path.exists(os.path.join(DATA_DIR, filename)):
            lines.append(f"| `{filename}` | 0 | — | {rules['fresh'][2]} | ⏳ No data yet |")
            continue
        column, max_age, cadence = rules["fresh"]
        count, last = latest(filename, column)
        status = "✅ OK"
        if filename in rejected:
            status = "❌ New data rejected by validation"
        elif max_age is not None and last:
            age = (today - date.fromisoformat(last[:10])).days
            if age > max_age:
                status = f"⚠️ Stale ({age} days old)"
                stale.append(filename)
        lines.append(f"| `{filename}` | {count:,} | {last} | {cadence} | {status} |")
    with open(os.path.join(REPO_ROOT, "STATUS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return stale


def main():
    rejected = {}
    for filename in sorted(os.listdir(DATA_DIR)):
        if not filename.endswith(".csv"):
            continue
        rules = RULES.get(filename)
        if rules is None:
            log(f"::warning::{filename} has no validation rules; add them to validate.py")
            continue
        errors = check_file(filename, rules)
        if errors:
            rejected[filename] = errors
            for e in errors[:10]:
                log(f"::error file=data/{filename}::{e}")
            if len(errors) > 10:
                log(f"::error file=data/{filename}::... and {len(errors) - 10} more")
            restore(filename)
            log(f"Validation: {filename} REJECTED ({len(errors)} problem(s)); changes reverted")
        else:
            log(f"Validation: {filename} ok")

    for filename in write_status(rejected):
        log(f"::warning::{filename} is stale; its source may have stopped updating")
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
