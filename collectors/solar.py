"""Collect yesterday's solar radiation and sunshine for Sri Lankan cities from Open-Meteo.

Writes to data/solar.csv, one row per (date, city).
"""

import sys
from datetime import timedelta

from common import CITIES, append_rows, fetch_open_meteo, log, sl_today

FIELDNAMES = ["date", "city", "latitude", "longitude", "radiation_kwh_m2",
              "sunshine_hours", "daylight_hours", "uv_index_max"]


def main():
    target = (sl_today() - timedelta(days=1)).isoformat()
    log(f"Solar: collecting {target} for {len(CITIES)} cities")
    try:
        responses = fetch_open_meteo(
            "https://api.open-meteo.com/v1/forecast", list(CITIES.values()),
            daily="shortwave_radiation_sum,sunshine_duration,daylight_duration,uv_index_max",
            past_days=1, forecast_days=1, timezone="Asia/Colombo",
        )
    except Exception as e:
        log(f"Solar: FAILED: {e}")
        return 1

    rows, missing = [], []
    for (city, (lat, lon)), resp in zip(CITIES.items(), responses):
        daily = resp.get("daily", {})
        times = daily.get("time", [])
        if target not in times:
            missing.append(city)
            continue
        i = times.index(target)
        radiation, sunshine, daylight, uv = (
            daily[v][i] for v in ("shortwave_radiation_sum", "sunshine_duration",
                                  "daylight_duration", "uv_index_max"))
        if None in (radiation, sunshine, daylight, uv):
            missing.append(city)
            continue
        rows.append({
            "date": target, "city": city, "latitude": lat, "longitude": lon,
            "radiation_kwh_m2": round(radiation / 3.6, 3),  # MJ/m² -> kWh/m²
            "sunshine_hours": round(sunshine / 3600, 2),
            "daylight_hours": round(daylight / 3600, 2),
            "uv_index_max": uv,
        })

    written = append_rows("solar.csv", FIELDNAMES, rows, ["date", "city"])
    log(f"Solar: {written} new row(s) written, {len(rows) - written} duplicate(s) skipped")
    if missing:
        log(f"Solar: no data for: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
