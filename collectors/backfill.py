"""One-off historical backfill for the daily Open-Meteo datasets.

Fills data/weather.csv, data/solar.csv and data/river_discharge.csv from
--start up to the day before the earliest row the daily collectors wrote,
using the Open-Meteo archive (same models the daily collectors use for past
days) and the Flood API (GloFAS). Rows already in the files are kept; the
files are rewritten sorted by date.

Run in two steps so the slow, rate-limited download can't clash with the
scheduled workflow's commits:

    python3 collectors/backfill.py fetch --cache /tmp/backfill   # ~80 min
    git pull --rebase
    python3 collectors/backfill.py merge --cache /tmp/backfill
    git add data/ && git commit && git push

`fetch` is resumable: each response is cached as a JSON file.
Free-tier limits (600 calls/min, 5,000/hour, 10,000/day, where one year of
daily data for one location counts as ~26 calls) set the pacing.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
from datetime import date, timedelta

from common import CITIES, DATA_DIR, fetch_json, log, sl_today
from river_discharge import FIELDNAMES as RIVER_FIELDS, RIVERS
from solar import FIELDNAMES as SOLAR_FIELDS
from weather import FIELDNAMES as WEATHER_FIELDS

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
WEATHER_VARS = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum",
                "wind_speed_10m_max", "relative_humidity_2m_mean",
                "shortwave_radiation_sum", "sunshine_duration", "daylight_duration"]
PACE_SECONDS = 20


def year_chunks(start, end):
    y = start.year
    while date(y, 1, 1) <= end:
        yield y, max(start, date(y, 1, 1)), min(end, date(y, 12, 31))
        y += 1


def tasks(start, end):
    """(cache_name, url) for every request the backfill needs."""
    for city, (lat, lon) in CITIES.items():
        for y, a, b in year_chunks(start, end):
            q = {"latitude": lat, "longitude": lon, "start_date": a, "end_date": b,
                 "daily": ",".join(WEATHER_VARS), "timezone": "Asia/Colombo"}
            yield f"weather_{city}_{y}", ARCHIVE + "?" + urllib.parse.urlencode(q)
    for river, (lat, lon) in RIVERS.items():
        for y, a, b in year_chunks(start, end):
            q = {"latitude": lat, "longitude": lon, "start_date": a, "end_date": b,
                 "daily": "river_discharge"}
            yield f"river_{river}_{y}", FLOOD + "?" + urllib.parse.urlencode(q)


def fetch(args):
    os.makedirs(args.cache, exist_ok=True)
    todo = [(n, u) for n, u in tasks(args.start, args.end)
            if not os.path.exists(os.path.join(args.cache, n + ".json"))]
    log(f"Backfill: {len(todo)} request(s) to fetch, ~{len(todo) * PACE_SECONDS // 60} min")
    for i, (name, url) in enumerate(todo, 1):
        # Wait out rate limits and network outages (up to ~30 min) rather than
        # abandoning a long run; cached responses make a restart cheap anyway.
        for attempt in range(30):
            try:
                data = fetch_json(url, timeout=60)
                break
            except RuntimeError as e:
                if attempt == 29:
                    raise
                reason = "rate limited" if "429" in str(e) else "network error"
                log(f"  {reason}; waiting 65s")
                time.sleep(65)
        with open(os.path.join(args.cache, name + ".json"), "w") as f:
            json.dump(data, f)
        log(f"  [{i}/{len(todo)}] {name}")
        if i < len(todo):
            time.sleep(PACE_SECONDS)


def cached(args, prefix, names):
    for name in names:
        for y, _, _ in year_chunks(args.start, args.end):
            path = os.path.join(args.cache, f"{prefix}_{name}_{y}.json")
            with open(path) as f:
                yield name, json.load(f)["daily"]


def merge_file(filename, fieldnames, rows, key_fields):
    """Add rows whose key is not in the file yet, then rewrite it sorted."""
    path = os.path.join(DATA_DIR, filename)
    existing = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    keys = {tuple(r[k] for k in key_fields) for r in existing}
    added = [r for r in rows if tuple(str(r[k]) for k in key_fields) not in keys]
    merged = existing + [{k: "" if r[k] is None else str(r[k]) for k in fieldnames} for r in added]
    merged.sort(key=lambda r: tuple(r[k] for k in key_fields))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)
    log(f"  {filename}: {len(added)} row(s) added, {len(merged)} total")


def merge(args):
    weather, solar, river = [], [], []
    for city, d in cached(args, "weather", CITIES):
        lat, lon = CITIES[city]
        for i, day in enumerate(d["time"]):
            v = {k: d[k][i] for k in WEATHER_VARS}
            if None not in (v["temperature_2m_max"], v["temperature_2m_min"],
                            v["precipitation_sum"], v["wind_speed_10m_max"],
                            v["relative_humidity_2m_mean"]):
                weather.append({"date": day, "city": city, "latitude": lat, "longitude": lon,
                                "temp_max_c": v["temperature_2m_max"],
                                "temp_min_c": v["temperature_2m_min"],
                                "precipitation_mm": v["precipitation_sum"],
                                "wind_speed_max_kmh": v["wind_speed_10m_max"],
                                "humidity_mean_pct": v["relative_humidity_2m_mean"]})
            if None not in (v["shortwave_radiation_sum"], v["sunshine_duration"],
                            v["daylight_duration"]):
                solar.append({"date": day, "city": city, "latitude": lat, "longitude": lon,
                              "radiation_kwh_m2": round(v["shortwave_radiation_sum"] / 3.6, 3),
                              "sunshine_hours": round(v["sunshine_duration"] / 3600, 2),
                              "daylight_hours": round(v["daylight_duration"] / 3600, 2),
                              "uv_index_max": None})  # not in the archive
    for name, d in cached(args, "river", RIVERS):
        lat, lon = RIVERS[name]
        for day, value in zip(d["time"], d["river_discharge"]):
            if value is not None:
                river.append({"date": day, "river": name, "latitude": lat,
                              "longitude": lon, "discharge_m3s": value})

    log("Backfill: merging")
    merge_file("weather.csv", WEATHER_FIELDS, weather, ["date", "city"])
    merge_file("solar.csv", SOLAR_FIELDS, solar, ["date", "city"])
    merge_file("river_discharge.csv", RIVER_FIELDS, river, ["date", "river"])


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("step", choices=["fetch", "merge"])
    p.add_argument("--cache", required=True, help="directory for cached API responses")
    p.add_argument("--start", type=date.fromisoformat, default=date(2020, 1, 1))
    p.add_argument("--end", type=date.fromisoformat,
                   default=sl_today() - timedelta(days=2),
                   help="last day to backfill (default: the day before yesterday)")
    args = p.parse_args()
    fetch(args) if args.step == "fetch" else merge(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
