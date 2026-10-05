"""Collect yesterday's complete daily weather for Sri Lankan cities from Open-Meteo.

Writes to data/weather.csv, one row per (date, city).
"""

import sys
import urllib.parse
from datetime import timedelta

from common import append_rows, fetch_json, iso, log, sl_today

CITIES = {
    "Wellawaya": (6.7378, 81.1031),
    "Colombo": (6.9271, 79.8612),
    "Kandy": (7.2906, 80.6337),
    "Galle": (6.0535, 80.2210),
    "Jaffna": (9.6615, 80.0255),
    "Nuwara Eliya": (6.9497, 80.7891),
    "Trincomalee": (8.5874, 81.2152),
}

# Open-Meteo daily variable -> CSV column
VARIABLES = {
    "temperature_2m_max": "temp_max_c",
    "temperature_2m_min": "temp_min_c",
    "precipitation_sum": "precipitation_mm",
    "wind_speed_10m_max": "wind_speed_max_kmh",
    "relative_humidity_2m_mean": "humidity_mean_pct",
}

FIELDNAMES = ["date", "city", "latitude", "longitude", *VARIABLES.values()]


def fetch_city(city, lat, lon, target_date):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(VARIABLES),
        "past_days": 1,
        "forecast_days": 1,
        "timezone": "Asia/Colombo",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    daily = fetch_json(url)["daily"]

    target = iso(target_date)
    if target not in daily["time"]:
        raise RuntimeError(f"{target} not in response dates {daily['time']}")
    i = daily["time"].index(target)

    row = {"date": target, "city": city, "latitude": lat, "longitude": lon}
    for var, col in VARIABLES.items():
        value = daily[var][i]
        if value is None:
            raise RuntimeError(f"missing {var} for {target}")
        row[col] = value
    return row


def main():
    yesterday = sl_today() - timedelta(days=1)
    log(f"Weather: collecting {yesterday} for {len(CITIES)} cities")

    rows, failed = [], []
    for city, (lat, lon) in CITIES.items():
        try:
            rows.append(fetch_city(city, lat, lon, yesterday))
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
