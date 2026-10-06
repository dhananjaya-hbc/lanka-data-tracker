"""Collect Colombo Stock Exchange (CSE) daily market data: the ASPI and
S&P Sri Lanka 20 indices plus turnover, share volume and trade count.

Uses the JSON endpoints behind cse.lk (unofficial, may change). Values during
trading hours are intraday; later runs on the same trade date overwrite them,
so the stored row ends as the closing value. Before the market opens some
endpoints return an empty body, and on non-trading days there are no trades;
both are skipped. Writes to data/cse_market.csv, one row per trade date.
"""

import json
import sys
from datetime import datetime

from common import SL_TZ, fetch_bytes, log, upsert_rows

API = "https://www.cse.lk/api/"
FIELDNAMES = ["date", "aspi", "aspi_change", "aspi_change_pct",
              "sp_sl20", "sp_sl20_change", "sp_sl20_change_pct",
              "turnover_lkr", "share_volume", "trades"]


def post(endpoint):
    """POST to a CSE endpoint; None if it has no data (empty body)."""
    body = fetch_bytes(API + endpoint, data=b"").strip()
    return json.loads(body) if body else None


def trade_date(ms):
    return datetime.fromtimestamp(ms / 1000, SL_TZ).date().isoformat()


def main():
    log("CSE: fetching ASPI, S&P SL20 and market summary")
    try:
        aspi, snp, summary = post("aspiData"), post("snpData"), post("marketSummery")
        if None in (aspi, snp, summary):
            log("CSE: no data yet (market not open); skipped")
            return 0
        if not summary.get("trades"):
            log(f"CSE: no trades on {trade_date(summary['tradeDate'])} (non-trading day); skipped")
            return 0
        row = {
            "date": trade_date(aspi["timestamp"]),
            "aspi": aspi["value"],
            "aspi_change": aspi["change"],
            "aspi_change_pct": round(aspi["percentage"], 4),
            "sp_sl20": snp["value"],
            "sp_sl20_change": snp["change"],
            "sp_sl20_change_pct": round(snp["percentage"], 4),
            "turnover_lkr": round(summary["tradeVolume"], 2),
            "share_volume": summary["shareVolume"],
            "trades": summary["trades"],
        }
        dates = {row["date"], trade_date(snp["timestamp"]), trade_date(summary["tradeDate"])}
        if len(dates) != 1:
            raise RuntimeError(f"endpoints disagree on trade date: {sorted(dates)}")
    except Exception as e:
        log(f"CSE: FAILED: {e}")
        return 1

    added, updated = upsert_rows("cse_market.csv", FIELDNAMES, [row], ["date"])
    log(f"CSE ({row['date']}): {added} added, {updated} updated, ASPI {row['aspi']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
