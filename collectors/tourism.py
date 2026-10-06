"""Collect monthly tourist arrivals from the Sri Lanka Tourism Development
Authority (SLTDA) weekly reports.

The latest weekly report's summary table lists arrivals per month for the
current year, last year and SLTDA's 2018 reference year. The current month is
partial until it ends: its row is updated with each report (`complete`
false, `as_of` = the last day counted) and marked complete once the month is
over. Each year's months must add up to the report's TOTAL row. Writes to
data/tourism.csv, one row per (year, month).
"""

import calendar
import re
import sys
from datetime import datetime

from common import fetch_bytes, fetch_text, log, sl_today, upsert_rows
from pdftext import pdf_cells

LIST_URL = "https://www.sltda.gov.lk/en/weekly-tourist-arrivals-reports-{year}"
PDF_LINK = re.compile(r"https://www\.sltda\.gov\.lk/storage/[^\"'\s]+\.pdf", re.I)
MONTHS = list(calendar.month_name)[1:]
NUMBER = re.compile(r"\d{1,3}(,\d{3})+|\d{1,3}")
FIELDNAMES = ["year", "month", "month_name", "arrivals", "complete", "as_of"]


def latest_report_url(today):
    """The newest report linked from this year's page (last year's in early January)."""
    for year in (today.year, today.year - 1):
        try:
            links = PDF_LINK.findall(fetch_text(LIST_URL.format(year=year)))
        except RuntimeError:
            continue
        if links:
            return links[-1]
    raise RuntimeError("no report links found on the SLTDA pages")


def parse(cells):
    """Return (as_of date, [rows]) from the report's summary table."""
    text = " ".join(cells)
    m = re.search(r"Tourist arrivals from \d+\w* to (\d+)\w* (" + "|".join(MONTHS) + r") (\d{4})", text)
    if not m:
        raise RuntimeError("report period not found")
    as_of = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").date()

    start = cells.index("Month")
    # the three year columns directly above "Month" (the period line also has a year)
    years = [int(c) for c in cells[max(0, start - 8):start] if re.fullmatch(r"\d{4}", c)][-3:]
    if len(years) != 3 or years[-1] != as_of.year:
        raise RuntimeError(f"unexpected year columns {years}")

    rows = []
    positions = [cells.index(name, start) for name in MONTHS]
    end = cells.index("TOTAL", start)
    for month, (pos, nxt) in enumerate(zip(positions, positions[1:] + [end]), 1):
        values = [int(c.replace(",", "")) for c in cells[pos + 1:nxt] if NUMBER.fullmatch(c)]
        for year, arrivals in zip(years, values[:3]):
            partial = ((year, month) == (as_of.year, as_of.month)
                       and as_of.day < calendar.monthrange(year, month)[1])
            rows.append({"year": year, "month": month, "month_name": MONTHS[month - 1],
                         "arrivals": arrivals, "complete": "false" if partial else "true",
                         "as_of": as_of.isoformat() if partial else ""})
    totals = [int(c.replace(",", "")) for c in cells[end + 1:end + 4] if NUMBER.fullmatch(c)]
    for year, total in zip(years, totals):
        months_sum = sum(r["arrivals"] for r in rows if r["year"] == year)
        if months_sum != total:
            raise RuntimeError(f"{year}: months add up to {months_sum}, report total is {total}")
    current = [r for r in rows if r["year"] == as_of.year]
    if not current or max(r["month"] for r in current) != as_of.month:
        raise RuntimeError("current month missing from the summary table")
    return as_of, rows


def main():
    log("Tourism: finding the latest SLTDA weekly report")
    try:
        url = latest_report_url(sl_today())
        as_of, rows = parse(pdf_cells(fetch_bytes(url, timeout=90)))
    except Exception as e:
        log(f"Tourism: FAILED: {e}")
        return 1
    added, updated = upsert_rows("tourism.csv", FIELDNAMES, rows, ["year", "month"])
    log(f"Tourism (to {as_of}): {added} added, {updated} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
