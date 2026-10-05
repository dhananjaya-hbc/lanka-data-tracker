"""Collect key rates from the Central Bank of Sri Lanka (CBSL) website:
CCPI headline inflation, the Overnight Policy Rate, and the USD/LKR
telegraphic-transfer buying and selling rates.

The page shows no date, and banks quote the TT rates at 9:30 a.m., so a row is
only recorded on weekdays from 10:00 Sri Lanka time and is labelled with that
day. Writes to data/cbsl_rates.csv, one row per date.
"""

import re
import sys
from datetime import datetime

from common import SL_TZ, fetch_text, html_to_text, log, upsert_rows

URL = "https://www.cbsl.gov.lk/cbsl_custom/param/ratewindow.php"
FIELDNAMES = ["date", "ccpi_inflation_pct", "overnight_policy_rate_pct",
              "usd_tt_buy", "usd_tt_sell"]

# column -> (regex on the flattened page, plausible range)
PATTERNS = {
    "ccpi_inflation_pct": (r"(-?[\d.]+) \| % \| \(CCPI\)", (-30, 100)),
    "overnight_policy_rate_pct": (r"\(CCPI\) \| ([\d.]+) ?%", (0, 50)),
    "usd_tt_buy": (r"TT Buy \| ([\d.]+)", (50, 2000)),
    "usd_tt_sell": (r"TT Sell \| ([\d.]+)", (50, 2000)),
}


def main():
    now = datetime.now(SL_TZ)
    if now.weekday() >= 5 or now.hour < 10:
        log(f"CBSL rates: skipped (rates for {now:%a %H:%M} Sri Lanka time not yet published)")
        return 0

    log("CBSL rates: fetching rate window")
    try:
        text = html_to_text(fetch_text(URL))
        row = {"date": now.date().isoformat()}
        for col, (pattern, (lo, hi)) in PATTERNS.items():
            m = re.search(pattern, text)
            if not m:
                raise RuntimeError(f"{col} not found; page layout may have changed")
            value = float(m.group(1))
            if not lo <= value <= hi:
                raise RuntimeError(f"{col}={value} outside plausible range {lo}..{hi}")
            row[col] = m.group(1)
    except Exception as e:
        log(f"CBSL rates: FAILED: {e}")
        return 1

    added, updated = upsert_rows("cbsl_rates.csv", FIELDNAMES, [row], ["date"])
    log(f"CBSL rates ({row['date']}): {added} added, {updated} updated -> {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
