"""Collect weekly dengue cases by district from the National Dengue Control
Unit (NDCU) weekly reports.

NDCU publishes one PDF per week; Table 1 lists cases per district/RDHS. Each
run lists the reports on the NDCU site, downloads any week not yet in the CSV,
and extracts Table 1 with a small standard-library PDF text reader. The first
run backfills every listed week.

Writes to data/dengue.csv, one row per (year, week, district). `cases` is the
count reported for that week (as first published; later reports may revise it
slightly) and `cumulative_cases` is the year-to-date total.

Report links come from the weekly-report pages and the homepage. If the
weekly-report page is down (it has returned 404 at times), the usual upload
address of the next few weeks' reports is checked directly instead.

Some reports embed Table 1 as an image. Table 1 also repeats the previous
week's counts, so such a week is filled from the following week's report;
`source_report_week` records which report each row came from.
"""

import csv
import os
import re
import sys
import urllib.request
from datetime import date, timedelta

from common import DATA_DIR, USER_AGENT, append_rows, fetch_bytes, fetch_text, log, sl_today
from pdftext import pdf_cells

LIST_URL = "https://www.dengue.health.gov.lk/weekly-report/"
HOME_URL = "https://www.dengue.health.gov.lk/"
UPLOADS = "https://www.dengue.health.gov.lk/wp-content/uploads"
GUESS_WEEKS = 3  # weeks after the newest known report to look for directly
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


def links_on(html):
    return {(int(y), int(w)): m.group(0) for m in PDF_LINK.finditer(html) for y, w in [m.groups()]}


def list_pages():
    """Reports linked from the weekly-report pages, or None if the list is down."""
    reports = {}
    for page in range(1, MAX_LIST_PAGES + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}page/{page}/"
        try:
            html = fetch_text(url, retries=1 if page > 1 else 3)
        except Exception as e:
            if page == 1:
                log(f"  weekly-report page unavailable: {e}")
                return None
            break  # ran past the last page
        found = links_on(html)
        if not set(found) - set(reports):
            break
        for key, link in found.items():
            reports.setdefault(key, link)
    return reports


def pdf_exists(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status == 200 and "pdf" in resp.headers.get("Content-Type", "")
    except Exception:
        return False


def guess_next(after, today):
    """Look for the reports of the weeks after `after` = (year, week) at their
    usual upload address. Reports appear 2-4 weeks after the week ends, in the
    upload folder of the month they were published."""
    found = {}
    start = date.fromisocalendar(after[0], after[1], 1)
    for k in range(1, GUESS_WEEKS + 1):
        week_start = start + timedelta(weeks=k)
        if week_start > today:
            break
        year, week, _ = week_start.isocalendar()
        folders = sorted({(d.year, d.month) for d in
                          (week_start + timedelta(days=n) for n in range(7, 43, 7)) if d <= today})
        for fy, fm in folders:
            for name in (f"Weekly-Dengue-Update-{year}-Week-{week}.pdf",
                         f"weekly-dengue-update-{year}-week-{week}.pdf"):
                url = f"{UPLOADS}/{fy}/{fm:02d}/{name}"
                if pdf_exists(url):
                    found[(year, week)] = url
                    break
            if (year, week) in found:
                break
    return found


def list_reports(stored):
    """{(year, week): pdf_url} from every source that is reachable."""
    reports = list_pages()
    list_ok = reports is not None
    reports = reports or {}
    try:
        for key, link in links_on(fetch_text(HOME_URL)).items():
            reports.setdefault(key, link)
    except Exception as e:
        log(f"  homepage unavailable: {e}")
        if not list_ok:
            raise RuntimeError("neither the weekly-report page nor the homepage could be read")
    if not list_ok:
        known = set(reports) | stored
        if known:
            guessed = guess_next(max(known), sl_today())
            log(f"  checked upload addresses directly: found {sorted(guessed) or 'nothing new'}")
            for key, link in guessed.items():
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
        stored = stored_weeks()
        reports = list_reports(stored)
    except Exception as e:
        log(f"Dengue: FAILED to list reports: {e}")
        return 1
    if not reports:
        log("Dengue: FAILED: no report links found; page layout may have changed")
        return 1

    latest = max(reports)
    todo = sorted(set(reports) - stored)
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
