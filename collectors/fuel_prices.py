"""Collect retail fuel prices from Ceylon Petroleum Corporation (CPC).

Scrapes CPC's historical price table, which lists every price revision, so the
first run backfills the full history and later runs add new revisions.
Writes to data/fuel_prices.csv, one row per (date, effective_time, product).
`date` is the day the price took effect; `effective_time` is only set when CPC
lists a time, which happens when prices changed twice on one day.
"""

import re
import sys
from datetime import datetime

from common import append_rows, fetch_text, log

URL = "https://ceypetco.gov.lk/historical-prices/"

# Table header -> product name
PRODUCTS = {
    "LP 95": "Lanka Petrol 95 Octane Euro 4",
    "LP 92": "Lanka Petrol 92 Octane",
    "LAD": "Lanka Auto Diesel",
    "LSD": "Lanka Super Diesel 4 Star Euro 4",
    "LK": "Lanka Kerosene",
    "LIK": "Lanka Industrial Kerosene",
    "FUR. 800": "Lanka Fuel Oil Super (800)",
    "FUR 1500 (High)": "Lanka Fuel Oil 1500 Sec (High Sulphur)",
    "FUR. 1500 (Low)": "Lanka Fuel Oil 1500 Sec (Low Sulphur)",
}

FIELDNAMES = ["date", "effective_time", "product_code", "product", "price_lkr_per_litre"]


def cells(row_html):
    return [re.sub(r"<[^>]+>|\s+", " ", c).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S | re.I)]


def parse(page):
    for table in re.findall(r"<table\b.*?</table>", page, re.S | re.I):
        rows = [cells(r) for r in re.findall(r"<tr\b.*?</tr>", table, re.S | re.I)]
        rows = [r for r in rows if r]
        # The page also has a bitumen table; the fuel one has these columns.
        if not rows or rows[0][0] != "Date" or "LP 92" not in rows[0]:
            continue
        header = rows[0][1:]
        unknown = [h for h in header if h not in PRODUCTS]
        if unknown:
            raise RuntimeError(f"unexpected columns {unknown}; update PRODUCTS")
        out = []
        for r in rows[1:]:
            # "01.10.2026" or "17.10.2022 (9.00 PM)"
            m = re.fullmatch(r"(\d\d\.\d\d\.\d{4})(?: \((\d{1,2})\.(\d\d) ([AP]M)\))?", r[0])
            if not m:
                raise RuntimeError(f"unrecognised date cell {r[0]!r}")
            day = datetime.strptime(m.group(1), "%d.%m.%Y").date().isoformat()
            when = ""
            if m.group(2):
                hour = int(m.group(2)) % 12 + (12 if m.group(4) == "PM" else 0)
                when = f"{hour:02d}:{m.group(3)}"
            for code, value in zip(header, r[1:]):
                value = value.replace(",", "")
                if not re.fullmatch(r"\d+(\.\d+)?", value):
                    continue  # blank or "-" for products not sold at the time
                out.append({"date": day, "effective_time": when, "product_code": code,
                            "product": PRODUCTS[code], "price_lkr_per_litre": value})
        return out
    raise RuntimeError("fuel price table not found on page")


def main():
    log("Fuel prices: fetching CPC historical prices")
    try:
        rows = parse(fetch_text(URL))
    except Exception as e:
        log(f"Fuel prices: FAILED: {e}")
        return 1
    rows.sort(key=lambda r: (r["date"], r["effective_time"], r["product_code"]))
    written = append_rows("fuel_prices.csv", FIELDNAMES, rows,
                          ["date", "effective_time", "product_code"])
    log(f"Fuel prices: {len(rows)} price(s) on page, {written} new row(s) written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
