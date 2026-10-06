"""Collect daily river discharge for major Sri Lankan rivers from the
Open-Meteo Flood API (GloFAS model).

Stores yesterday plus any missing day in the previous LOOKBACK_DAYS days.
Writes to data/river_discharge.csv, one row per (date, river).
"""

import sys
from datetime import timedelta

from common import LOOKBACK_DAYS, append_rows, fetch_open_meteo, log, sl_today

# GloFAS grid cells on each river's main channel, chosen as the cell with the
# highest median discharge near a lower-basin gauging station.
RIVERS = {
    "Kelani Ganga": (6.925, 79.975),
    "Kalu Ganga": (6.575, 79.975),
    "Mahaweli Ganga": (7.875, 81.025),
    "Gin Ganga": (6.075, 80.125),
    "Nilwala Ganga": (5.925, 80.525),
    "Walawe Ganga": (6.125, 80.975),
    "Deduru Oya": (7.625, 79.775),
    "Kala Oya": (8.225, 79.925),
}

FIELDNAMES = ["date", "river", "latitude", "longitude", "discharge_m3s"]


def main():
    yesterday = sl_today() - timedelta(days=1)
    target = yesterday.isoformat()
    log(f"River discharge: collecting the {LOOKBACK_DAYS} days to {target} for {len(RIVERS)} rivers")
    try:
        responses = fetch_open_meteo(
            "https://flood-api.open-meteo.com/v1/flood", list(RIVERS.values()),
            daily="river_discharge", past_days=LOOKBACK_DAYS, forecast_days=1,
        )
    except Exception as e:
        log(f"River discharge: FAILED: {e}")
        return 1

    rows, missing = [], []
    for (river, (lat, lon)), resp in zip(RIVERS.items(), responses):
        daily = resp.get("daily", {})
        days = [(d, v) for d, v in zip(daily.get("time", []), daily.get("river_discharge", []))
                if d <= target and v is not None]
        if not any(d == target for d, _ in days):
            missing.append(river)
        rows += [{"date": d, "river": river, "latitude": lat, "longitude": lon,
                  "discharge_m3s": v} for d, v in days]

    written = append_rows("river_discharge.csv", FIELDNAMES, rows, ["date", "river"])
    log(f"River discharge: {written} new row(s) written, {len(rows) - written} duplicate(s) skipped")
    if missing:
        log(f"River discharge: no data for: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
