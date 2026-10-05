"""Snapshot current weather conditions for Sri Lankan cities from Open-Meteo.

Runs every 4 hours. Writes to data/weather_snapshots.csv, one row per (time, city).
"""

import sys

from common import CITIES, collect_current

VARIABLES = {
    "temperature_2m": "temp_c",
    "apparent_temperature": "feels_like_c",
    "relative_humidity_2m": "humidity_pct",
    "precipitation": "precipitation_mm",
    "cloud_cover": "cloud_cover_pct",
    "wind_speed_10m": "wind_speed_kmh",
    "wind_direction_10m": "wind_direction_deg",
    "uv_index": "uv_index",
}

if __name__ == "__main__":
    sys.exit(collect_current(
        "Weather snapshots", "weather_snapshots.csv",
        "https://api.open-meteo.com/v1/forecast", CITIES, VARIABLES,
    ))
