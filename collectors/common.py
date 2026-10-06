"""Shared helpers for the collectors: HTTP with retries, CSV dedupe/append, dates.

Standard library only.
"""

import csv
import html
import json
import os
import re
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

# Daily collectors re-request this many past days and add any that are
# missing, so dropped or delayed workflow runs never leave gaps.
LOOKBACK_DAYS = 7

USER_AGENT = "lanka-data-tracker/1.0 (+https://github.com/dhananjaya-hbc/lanka-data-tracker)"

# City -> (latitude, longitude), shared by the land-based collectors:
# every district capital, plus Wellawaya.
CITIES = {
    "Wellawaya": (6.7378, 81.1031),
    "Colombo": (6.9271, 79.8612),
    "Kandy": (7.2906, 80.6337),
    "Galle": (6.0535, 80.2210),
    "Jaffna": (9.6615, 80.0255),
    "Nuwara Eliya": (6.9497, 80.7891),
    "Trincomalee": (8.5874, 81.2152),
    "Gampaha": (7.0917, 79.9997),
    "Kalutara": (6.5854, 79.9607),
    "Matale": (7.4675, 80.6234),
    "Matara": (5.9549, 80.5550),
    "Hambantota": (6.1241, 81.1185),
    "Kilinochchi": (9.3803, 80.3770),
    "Mannar": (8.9810, 79.9044),
    "Vavuniya": (8.7514, 80.4971),
    "Mullaitivu": (9.2671, 80.8142),
    "Batticaloa": (7.7310, 81.6747),
    "Ampara": (7.2975, 81.6820),
    "Kurunegala": (7.4863, 80.3623),
    "Puttalam": (8.0362, 79.8283),
    "Anuradhapura": (8.3114, 80.4037),
    "Polonnaruwa": (7.9403, 81.0188),
    "Badulla": (6.9934, 81.0550),
    "Monaragala": (6.8728, 81.3507),
    "Ratnapura": (6.6828, 80.3992),
    "Kegalle": (7.2513, 80.3464),
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


def fetch_bytes(url, data=None, retries=3, timeout=30, backoff=2.0):
    """GET (or POST, if `data` is given) a URL and return the body as bytes.
    On failure, retry `retries` times with exponential backoff before raising
    the last error."""
    last_err = None
    for attempt in range(1, retries + 2):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt > retries:
                break
            wait = backoff ** attempt
            log(f"  request failed (attempt {attempt}/{retries + 1}): {e}; retrying in {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}: {last_err}")


def fetch_json(url, data=None, **kwargs):
    """Fetch a URL (POST if `data` is given) and parse the body as JSON."""
    return json.loads(fetch_bytes(url, data=data, **kwargs))


def fetch_text(url, **kwargs):
    """Fetch a URL and decode the body as UTF-8 text (e.g. an HTML page)."""
    return fetch_bytes(url, **kwargs).decode("utf-8", errors="replace")


def html_to_text(page):
    """Flatten HTML to text with " | " between elements, so values in
    adjacent tags stay separable by a regex."""
    page = re.sub(r"<(script|style)\b.*?</\1>", "", page, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "|", page))
    return re.sub(r"\s*\|[\s|]*", " | ", text)


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


def upsert_rows(filename, fieldnames, rows, key_fields):
    """Like append_rows, but a row whose key already exists replaces the stored
    row when any value differs (for sources that revise published figures).
    Existing row order is kept and new rows go at the end.
    Returns (added, updated)."""
    path = os.path.join(DATA_DIR, filename)
    os.makedirs(DATA_DIR, exist_ok=True)

    stored = {}
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                stored[tuple(r[k] for k in key_fields)] = r

    added = updated = 0
    for r in rows:
        r = {k: "" if r[k] is None else str(r[k]) for k in fieldnames}
        key = tuple(r[k] for k in key_fields)
        if key not in stored:
            added += 1
        elif stored[key] != r:
            updated += 1
        else:
            continue
        stored[key] = r

    if added or updated:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(stored.values())
    return added, updated


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
