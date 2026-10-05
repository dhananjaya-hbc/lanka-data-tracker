"""Shared helpers for the collectors: HTTP with retries, CSV dedupe/append, dates.

Standard library only.
"""

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

# Sri Lanka has no DST, so a fixed offset avoids depending on tzdata.
SL_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Colombo")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")

USER_AGENT = "lanka-data-tracker/1.0 (+https://github.com/dhananjaya-hbc/lanka-data-tracker)"

# City -> (latitude, longitude), shared by the land-based collectors.
CITIES = {
    "Wellawaya": (6.7378, 81.1031),
    "Colombo": (6.9271, 79.8612),
    "Kandy": (7.2906, 80.6337),
    "Galle": (6.0535, 80.2210),
    "Jaffna": (9.6615, 80.0255),
    "Nuwara Eliya": (6.9497, 80.7891),
    "Trincomalee": (8.5874, 81.2152),
}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def sl_today():
    """Today's date in Sri Lanka."""
    return datetime.now(SL_TZ).date()


def fetch_open_meteo(base_url, points, **params):
    """Query an Open-Meteo API for several (lat, lon) points in one request.
    Returns one response dict per point, in the same order."""
    query = {
        "latitude": ",".join(str(lat) for lat, _ in points),
        "longitude": ",".join(str(lon) for _, lon in points),
        **params,
    }
    data = fetch_json(base_url + "?" + urllib.parse.urlencode(query))
    return data if isinstance(data, list) else [data]


def fetch_json(url, retries=3, timeout=30, backoff=2.0):
    """GET a URL and parse JSON. On failure, retry `retries` times with
    exponential backoff before raising the last error."""
    last_err = None
    for attempt in range(1, retries + 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            last_err = e
            if attempt > retries:
                break
            wait = backoff ** attempt
            log(f"  request failed (attempt {attempt}/{retries + 1}): {e}; retrying in {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}: {last_err}")


def append_rows(filename, fieldnames, rows, key_fields):
    """Append rows to data/<filename>, skipping any whose key (tuple of
    key_fields) already exists in the file or earlier in `rows`.
    Creates the file with a header if needed. Returns the number of rows written."""
    path = os.path.join(DATA_DIR, filename)
    os.makedirs(DATA_DIR, exist_ok=True)

    seen = set()
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    if exists:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                seen.add(tuple(r[k] for k in key_fields))

    new_rows = []
    for r in rows:
        key = tuple(str(r[k]) for k in key_fields)
        if key in seen:
            continue
        seen.add(key)
        new_rows.append(r)

    if new_rows:
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerows(new_rows)
    return len(new_rows)


def collect_current(label, filename, base_url, points, variables, location_field="city"):
    """Snapshot an Open-Meteo `current=` endpoint for named points and append
    one row per (time, location) to data/<filename>.

    points:    {name: (lat, lon)}
    variables: {open-meteo variable: CSV column}
    Returns a process exit code (0 ok, 1 failed)."""
    fieldnames = ["time", location_field, "latitude", "longitude", *variables.values()]
    log(f"{label}: snapshotting {len(points)} locations")
    try:
        responses = fetch_open_meteo(
            base_url, list(points.values()),
            current=",".join(variables), timezone="Asia/Colombo",
        )
    except Exception as e:
        log(f"{label}: FAILED: {e}")
        return 1

    rows, empty = [], []
    for (name, (lat, lon)), resp in zip(points.items(), responses):
        cur = resp.get("current", {})
        values = {col: cur.get(var) for var, col in variables.items()}
        if not cur.get("time") or all(v is None for v in values.values()):
            empty.append(name)
            continue
        row = {"time": cur["time"], location_field: name, "latitude": lat, "longitude": lon}
        row.update({col: "" if v is None else v for col, v in values.items()})
        rows.append(row)

    written = append_rows(filename, fieldnames, rows, ["time", location_field])
    log(f"{label}: {written} new row(s) written, {len(rows) - written} duplicate(s) skipped")
    if empty:
        log(f"{label}: no data for: {', '.join(empty)}")
        return 1
    return 0


def iso(d):
    return d.isoformat() if isinstance(d, date) else str(d)
