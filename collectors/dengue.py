"""Collect weekly dengue cases by district from the National Dengue Control
Unit (NDCU) weekly reports.

NDCU publishes one PDF per week; Table 1 lists cases per district/RDHS. Each
run lists the reports on the NDCU site, downloads any week not yet in the CSV,
and extracts Table 1 with a small standard-library PDF text reader. The first
run backfills every listed week.

Writes to data/dengue.csv, one row per (year, week, district). `cases` is the
count reported for that week (as first published; later reports may revise it
slightly) and `cumulative_cases` is the year-to-date total.

Some reports embed Table 1 as an image. Table 1 also repeats the previous
week's counts, so such a week is filled from the following week's report;
`source_report_week` records which report each row came from.
"""

import csv
import os
import re
import sys
import zlib
from datetime import date

from common import DATA_DIR, append_rows, fetch_bytes, fetch_text, log

LIST_URL = "https://www.dengue.health.gov.lk/weekly-report/"
MAX_LIST_PAGES = 10
PDF_LINK = re.compile(
    r"https://[^\"'\s]+/weekly-dengue-update-(\d{4})-week-(\d+)[^\"'\s/]*\.pdf", re.I)

# 25 districts, with Ampara split into the Ampara and Kalmunai RDHS areas.
DISTRICTS = [
    "Colombo", "Gampaha", "Kalutara", "Kandy", "Matale", "Nuwara Eliya", "Galle",
    "Hambantota", "Matara", "Jaffna", "Kilinochchi", "Mannar", "Vavuniya",
    "Mullaitivu", "Batticaloa", "Ampara", "Trincomalee", "Kalmunai", "Kurunegala",
    "Puttalam", "Anuradhapura", "Polonnaruwa", "Badulla", "Monaragala",
    "Ratnapura", "Kegalle",
]

FIELDNAMES = ["year", "week", "week_start", "week_end", "district", "cases",
              "cumulative_cases", "source_report_week"]


# --- minimal PDF text extraction (FlateDecode streams + ToUnicode maps) -----

def _streams(pdf):
    for m in re.finditer(rb"stream\r?\n", pdf):
        end = pdf.find(b"endstream", m.end())
        if end < 0:
            continue
        try:
            yield zlib.decompress(pdf[m.end():end].rstrip(b"\r\n"))
        except zlib.error:
            continue


def _unicode_map(streams):
    cmap = {}
    for data in streams:
        for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
            for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
                cmap[src.upper()] = bytes.fromhex(dst.decode()).decode("utf-16-be", "ignore")
        for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
            for lo, hi, dst in re.findall(
                    rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
                width, start, base = len(lo), int(lo, 16), int(dst, 16)
                for k in range(int(hi, 16) - start + 1):
                    cmap[b"%0*X" % (width, start + k)] = chr(base + k)
    return cmap


def pdf_cells(pdf):
    """Return the PDF's text as a list of cells. Within a content stream,
    fragments of one cell are drawn back to back and cells are separated by a
    whitespace-only string, which is how the NDCU tables are laid out."""
    streams = list(_streams(pdf))
    cmap = _unicode_map(streams)
    cells, current = [], ""
    token = re.compile(rb"<([0-9A-Fa-f]+)>|\(((?:\\.|[^\\)])*)\)")
    for data in streams:
        if b"Tj" not in data and b"TJ" not in data:
            continue
        for m in token.finditer(data):
            if m.group(1) is not None:
                h = m.group(1).upper()
                piece = "".join(cmap.get(h[i:i + 4], "") for i in range(0, len(h), 4))
            else:
                piece = re.sub(r"\\(.)", r"\1", m.group(2).decode("latin-1"))
            if piece.strip():
                current += piece
            elif current:
                cells.append(current.strip())
                current = ""
    if current:
        cells.append(current.strip())
    return cells


# --- Table 1 parsing --------------------------------------------------------

def _number(cell):
    cell = cell.replace("*", "").replace(",", "").strip()
    if cell.lower() in ("nil", "ni"):  # "Ni" is a typo in some reports
        return 0
    return int(cell) if cell.isdigit() else None


def parse_table(cells):
    """Return ({district: (cases_previous_week, cases_this_week,
    cumulative_this_year)}, total_row). Each Table 1 row is: name, last year
    wk-1, last year wk, this year wk-1, this year wk, last year cumulative,
    this year cumulative."""
    rows = {}
    for i, cell in enumerate(cells):
        name = cell.replace("*", "").strip()
        if name not in DISTRICTS and name != "Total":
            continue
        values = [_number(c) for c in cells[i + 1:i + 7]]
        if len(values) == 6 and None not in values and name not in rows:
            rows[name] = (values[2], values[3], values[5])
    missing = [d for d in DISTRICTS if d not in rows]
    if missing or "Total" not in rows:
        raise RuntimeError(f"Table 1 incomplete; missing {missing or ['Total']}")
    return rows, rows.pop("Total")


def checked(parsed, col):
    """Return the table after checking that column `col` (0 = previous week,
    1 = this week) of the districts adds up to the Total row."""
    table, total = parsed
    col_sum = sum(v[col] for v in table.values())
    if col_sum != total[col]:
        raise RuntimeError(f"district sum {col_sum} != reported total {total[col]}")
    return table


def list_reports():
    """{(year, week): pdf_url} for every report linked from the NDCU site."""
    reports = {}
    for page in range(1, MAX_LIST_PAGES + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}page/{page}/"
        try:
            html = fetch_text(url, retries=1 if page > 1 else 3)
        except Exception:
            if page == 1:
                raise
            break  # ran past the last page
        found = {(int(y), int(w)): m.group(0) for m in PDF_LINK.finditer(html)
                 for y, w in [m.groups()]}
        if not set(found) - set(reports):
            break
        for key, link in found.items():
            reports.setdefault(key, link)
    return reports


def stored_weeks():
    path = os.path.join(DATA_DIR, "dengue.csv")
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {(int(r["year"]), int(r["week"])) for r in csv.DictReader(f)}


def make_rows(year, week, source_week, counts):
    """counts: {district: (cases, cumulative)}"""
    start = date.fromisocalendar(year, week, 1)
    end = date.fromisocalendar(year, week, 7)
    return [{"year": year, "week": week, "week_start": start, "week_end": end,
             "district": d, "cases": c, "cumulative_cases": cum,
             "source_report_week": source_week}
            for d, (c, cum) in counts.items()]


def main():
    log("Dengue: listing NDCU weekly reports")
    try:
        reports = list_reports()
    except Exception as e:
        log(f"Dengue: FAILED to list reports: {e}")
        return 1
    if not reports:
        log("Dengue: FAILED: no report links found; page layout may have changed")
        return 1

    latest = max(reports)
    todo = sorted(set(reports) - stored_weeks())
    log(f"Dengue: {len(reports)} reports listed (latest {latest[0]} week {latest[1]}), "
        f"{len(todo)} new")

    tables, failed = {}, []

    def table_for(key):
        if key not in tables:
            tables[key] = parse_table(pdf_cells(fetch_bytes(reports[key], timeout=60)))
        return tables[key]

    rows = []
    for year, week in todo:
        try:
            table = checked(table_for((year, week)), 1)
        except Exception as e:
            failed.append((year, week))
            log(f"  FAIL {year} week {week}: {e}")
            continue
        rows += make_rows(year, week, week, {d: (c, cum) for d, (_, c, cum) in table.items()})
        log(f"  ok   {year} week {week}: {sum(v[1] for v in table.values())} cases")

    # Fill unreadable weeks from the next week's report ("previous week" column).
    for year, week in list(failed):
        nxt = (year, week + 1)
        if nxt not in reports:
            continue
        try:
            table = checked(table_for(nxt), 0)
        except Exception as e:
            log(f"  FAIL {year} week {week}: fallback to week {week + 1} report failed: {e}")
            continue
        # cumulative at week N = cumulative at N+1 minus cases in N+1
        rows += make_rows(year, week, week + 1,
                          {d: (prev, cum - cur) for d, (prev, cur, cum) in table.items()})
        failed.remove((year, week))
        log(f"  ok   {year} week {week}: {sum(v[0] for v in table.values())} cases "
            f"(from week {week + 1} report)")

    rows.sort(key=lambda r: (r["year"], r["week"]))
    written = append_rows("dengue.csv", FIELDNAMES, rows, ["year", "week", "district"])
    log(f"Dengue: {written} new row(s) written")
    if failed:
        log(f"Dengue: unreadable weeks: {', '.join(f'{y}-W{w}' for y, w in failed)}")
    # One unreadable week is usually an image table that the next report will
    # fill in, so it is only a warning. Two unreadable weeks in a row at the
    # head of the list means the layout changed, which needs fixing.
    if latest in failed and (latest[0], latest[1] - 1) in failed:
        log("Dengue: FAILED: the two newest reports are unreadable; layout may have changed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
