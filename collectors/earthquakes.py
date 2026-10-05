"""Collect earthquakes in the Sri Lanka / central Indian Ocean region from the
USGS earthquake catalogue.

Looks back 7 days on every run (dedupe on the USGS event id), so a missed run
never loses an event. Writes to data/earthquakes.csv, one row per event.
Magnitudes are as first reported; USGS may revise them later.
"""

import math
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

from common import SL_TZ, append_rows, fetch_json, log

REGION = {"minlatitude": -2, "maxlatitude": 14, "minlongitude": 72, "maxlongitude": 90}
MIN_MAGNITUDE = 3.0
LOOKBACK_DAYS = 7
COLOMBO = (6.9271, 79.8612)

FIELDNAMES = ["id", "time_utc", "time_local", "magnitude", "mag_type", "depth_km",
              "latitude", "longitude", "distance_to_colombo_km", "place", "url"]


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def main():
    start = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    params = {"format": "geojson", "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
              "minmagnitude": MIN_MAGNITUDE, "orderby": "time-asc", **REGION}
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode(params)
    log(f"Earthquakes: querying M{MIN_MAGNITUDE}+ events since {start:%Y-%m-%d}")
    try:
        features = fetch_json(url)["features"]
    except Exception as e:
        log(f"Earthquakes: FAILED: {e}")
        return 1

    rows = []
    for f in features:
        p = f["properties"]
        lon, lat, depth = f["geometry"]["coordinates"]
        t = datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc)
        rows.append({
            "id": f["id"],
            "time_utc": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_local": t.astimezone(SL_TZ).strftime("%Y-%m-%dT%H:%M:%S"),
            "magnitude": p["mag"],
            "mag_type": p.get("magType") or "",
            "depth_km": depth,
            "latitude": lat,
            "longitude": lon,
            "distance_to_colombo_km": round(haversine_km(lat, lon, *COLOMBO)),
            "place": p.get("place") or "",
            "url": p.get("url") or "",
        })

    written = append_rows("earthquakes.csv", FIELDNAMES, rows, ["id"])
    log(f"Earthquakes: {len(rows)} event(s) in window, {written} new row(s) written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
