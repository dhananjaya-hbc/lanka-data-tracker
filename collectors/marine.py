"""Snapshot current sea conditions off the Sri Lankan coast from the
Open-Meteo Marine API.

Runs every 4 hours. Writes to data/marine.csv, one row per (time, location).
"""

import sys

from common import collect_current

# Offshore points (a little out to sea so they fall on ocean grid cells).
LOCATIONS = {
    "Colombo": (6.93, 79.78),
    "Kalpitiya": (8.23, 79.70),
    "Jaffna": (9.85, 80.10),
    "Trincomalee": (8.60, 81.27),
    "Batticaloa": (7.73, 81.75),
    "Hambantota": (6.08, 81.13),
    "Galle": (5.98, 80.22),
}

VARIABLES = {
    "wave_height": "wave_height_m",
    "wave_period": "wave_period_s",
    "wave_direction": "wave_direction_deg",
    "swell_wave_height": "swell_wave_height_m",
    "sea_surface_temperature": "sea_surface_temp_c",
}

if __name__ == "__main__":
    sys.exit(collect_current(
        "Marine", "marine.csv",
        "https://marine-api.open-meteo.com/v1/marine", LOCATIONS, VARIABLES,
        location_field="location",
    ))
