"""Collect complete daily weather for Sri Lankan cities from Open-Meteo.

Stores yesterday plus any of the previous LOOKBACK_DAYS days that are missing
(so a dropped workflow run leaves no gap). Writes to data/weather.csv, one row
per (date, city).
"""

import sys
import urllib.parse
from datetime import timedelta

from common import CITIES, LOOKBACK_DAYS, append_rows, fetch_json, iso, log, sl_today

# Open-Meteo daily variable -> CSV column
VARIABLES = {
    "temperature_2m_max": "temp_max_c",
    "temperature_2m_min": "temp_min_c",
    "precipitation_sum": "precipitation_mm",
    "wind_speed_10m_max": "wind_speed_max_kmh",
    "relative_humidity_2m_mean": "humidity_mean_pct",
}

FIELDNAMES = ["date", "city", "latitude", "longitude", *VARIABLES.values()]


def fetch_city(city, lat, lon, today):
    """Rows for every complete day (before `today`) in the lookback window."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(VARIABLES),
        "past_days": LOOKBACK_DAYS,
        "forecast_days": 1,
        "timezone": "Asia/Colombo",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    daily = fetch_json(url)["daily"]

    yesterday = iso(today - timedelta(days=1))
    if yesterday not in daily["time"]:
        raise RuntimeError(f"{yesterday} not in response dates {daily['time']}")

    rows = []
    for i, day in enumerate(daily["time"]):
        values = {col: daily[var][i] for var, col in VARIABLES.items()}
        if day >= iso(today) or None in values.values():
            continue  # today is incomplete
        rows.append({"date": day, "city": city, "latitude": lat, "longitude": lon, **values})
    if not any(r["date"] == yesterday for r in rows):
        raise RuntimeError(f"missing values for {yesterday}")
    return rows


def main():
    today = sl_today()
    log(f"Weather: collecting the {LOOKBACK_DAYS} days to {today - timedelta(days=1)} "
        f"for {len(CITIES)} cities")

    rows, failed = [], []
    for city, (lat, lon) in CITIES.items():
        try:
            rows += fetch_city(city, lat, lon, today)
            log(f"  ok   {city}")
        except Exception as e:
            failed.append(city)
            log(f"  FAIL {city}: {e}")

    written = append_rows("weather.csv", FIELDNAMES, rows, ["date", "city"])
    log(f"Weather: {written} new row(s) written, {len(rows) - written} duplicate(s) skipped")

    if failed:
        log(f"Weather: failed cities: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
