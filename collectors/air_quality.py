"""Snapshot current air quality for Sri Lankan cities from the Open-Meteo
Air Quality API (CAMS model).

Runs every 4 hours. Writes to data/air_quality.csv, one row per (time, city).
Pollutant concentrations are in μg/m³.
"""

import sys

from common import CITIES, collect_current

VARIABLES = {
    "us_aqi": "us_aqi",
    "pm2_5": "pm2_5",
    "pm10": "pm10",
    "carbon_monoxide": "carbon_monoxide",
    "nitrogen_dioxide": "nitrogen_dioxide",
    "sulphur_dioxide": "sulphur_dioxide",
    "ozone": "ozone",
}

if __name__ == "__main__":
    sys.exit(collect_current(
        "Air quality", "air_quality.csv",
        "https://air-quality-api.open-meteo.com/v1/air-quality", CITIES, VARIABLES,
    ))
