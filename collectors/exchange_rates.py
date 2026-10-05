"""Collect LKR exchange rates from open.er-api.com.

Writes to data/exchange_rates.csv, one row per (date, currency), where
lkr_per_unit is how many Sri Lankan rupees buy 1 unit of the currency.
`date` is the UTC date the provider last updated its rates, so a stale
response is never stored under a newer date.
"""

import sys
from datetime import datetime, timezone

from common import append_rows, fetch_json, log

URL = "https://open.er-api.com/v6/latest/USD"
CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CNY", "AED"]
FIELDNAMES = ["date", "currency", "lkr_per_unit", "source_updated_utc"]


def main():
    log("Exchange rates: fetching USD base rates")
    try:
        data = fetch_json(URL)
        if data.get("result") != "success":
            raise RuntimeError(f"API returned result={data.get('result')!r}")
        rates = data["rates"]
        updated = datetime.fromtimestamp(data["time_last_update_unix"], tz=timezone.utc)
    except Exception as e:
        log(f"Exchange rates: FAILED: {e}")
        return 1

    lkr_per_usd = rates["LKR"]
    rows, missing = [], []
    for cur in CURRENCIES:
        if cur not in rates or not rates[cur]:
            missing.append(cur)
            continue
        rows.append({
            "date": updated.date().isoformat(),
            "currency": cur,
            "lkr_per_unit": round(lkr_per_usd / rates[cur], 6),
            "source_updated_utc": updated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    written = append_rows("exchange_rates.csv", FIELDNAMES, rows, ["date", "currency"])
    log(f"Exchange rates ({updated.date()}): {written} new row(s) written, "
        f"{len(rows) - written} duplicate(s) skipped")

    if missing:
        log(f"Exchange rates: missing currencies: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
