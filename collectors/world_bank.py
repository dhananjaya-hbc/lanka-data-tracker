"""Collect annual macroeconomic indicators for Sri Lanka from the World Bank API.

The World Bank revises past figures, so existing rows are updated in place when
a value changes. Writes to data/economy_indicators.csv, one row per
(year, indicator_id).
"""

import sys

from common import fetch_json, log, upsert_rows

INDICATORS = [
    "NY.GDP.MKTP.KD.ZG",   # GDP growth (annual %)
    "NY.GDP.MKTP.CD",      # GDP (current US$)
    "NY.GDP.PCAP.CD",      # GDP per capita (current US$)
    "FP.CPI.TOTL.ZG",      # Inflation, consumer prices (annual %)
    "SL.UEM.TOTL.ZS",      # Unemployment (% of labour force, ILO estimate)
    "BN.CAB.XOKA.GD.ZS",   # Current account balance (% of GDP)
    "NE.EXP.GNFS.ZS",      # Exports of goods and services (% of GDP)
    "NE.IMP.GNFS.ZS",      # Imports of goods and services (% of GDP)
    "BX.TRF.PWKR.CD.DT",   # Personal remittances received (current US$)
    "ST.INT.ARVL",         # International tourism, number of arrivals
    "FI.RES.TOTL.CD",      # Total reserves incl. gold (current US$)
    "PA.NUS.FCRF",         # Official exchange rate (LKR per US$, period average)
    "SP.POP.TOTL",         # Population, total
]

URL = "https://api.worldbank.org/v2/country/LKA/indicator/{}?format=json&per_page=200&date=1990:2100"
FIELDNAMES = ["year", "indicator_id", "indicator", "value"]


def main():
    log(f"World Bank: fetching {len(INDICATORS)} indicators")
    rows, failed = [], []
    for ind in INDICATORS:
        try:
            meta, records = fetch_json(URL.format(ind))[:2]
            for r in records or []:
                if r["value"] is not None:
                    rows.append({"year": r["date"], "indicator_id": ind,
                                 "indicator": r["indicator"]["value"], "value": r["value"]})
        except Exception as e:
            failed.append(ind)
            log(f"  FAIL {ind}: {e}")

    rows.sort(key=lambda r: (r["indicator_id"], r["year"]))
    added, updated = upsert_rows("economy_indicators.csv", FIELDNAMES, rows,
                                 ["year", "indicator_id"])
    log(f"World Bank: {len(rows)} values, {added} added, {updated} revised")
    if failed:
        log(f"World Bank: failed indicators: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
