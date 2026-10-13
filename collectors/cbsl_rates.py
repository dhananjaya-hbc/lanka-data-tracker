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

from common import BROWSER_HEADERS, SL_TZ, fetch_text, html_to_text, log, upsert_rows

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


def parse(page):
    """Extract the rates from the rate-window HTML: {column: value string}."""
    text = html_to_text(page)
    values = {}
    for col, (pattern, (lo, hi)) in PATTERNS.items():
        m = re.search(pattern, text)
        if not m:
            raise RuntimeError(f"{col} not found; page layout may have changed")
        value = float(m.group(1))
        if not lo <= value <= hi:
            raise RuntimeError(f"{col}={value} outside plausible range {lo}..{hi}")
        values[col] = m.group(1)
    return values


def main():
    now = datetime.now(SL_TZ)
    if now.weekday() >= 5 or now.hour < 10:
        log(f"CBSL rates: skipped (rates for {now:%a %H:%M} Sri Lanka time not yet published)")
        return 0

    log("CBSL rates: fetching rate window")
    try:
        try:
            page = fetch_text(URL)
        except RuntimeError as e:
            if "403" not in str(e):
                raise
            # CBSL's firewall sometimes refuses automated clients; the page is
            # public, so retry once the way an ordinary browser asks for it.
            log("CBSL rates: 403 Forbidden; retrying with browser-style headers")
            try:
                page = fetch_text(URL, headers=BROWSER_HEADERS)
            except RuntimeError as e2:
                if "403" not in str(e2):
                    raise
                # CBSL is refusing this network (seen from GitHub's servers since
                # 12 Oct 2026). Nothing we can fix, so warn instead of failing the
                # run; STATUS.md flags the dataset stale after 5 days.
                log("::warning::CBSL rates: still 403 Forbidden; CBSL is blocking this network, "
                    "no row saved today")
                return 0
        row = {"date": now.date().isoformat(), **parse(page)}
    except Exception as e:
        log(f"CBSL rates: FAILED: {e}")
        return 1

    added, updated = upsert_rows("cbsl_rates.csv", FIELDNAMES, [row], ["date"])
    log(f"CBSL rates ({row['date']}): {added} added, {updated} updated -> {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
