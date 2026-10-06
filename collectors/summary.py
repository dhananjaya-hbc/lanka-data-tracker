"""Write the "This week in Sri Lanka" section of README.md from the datasets.

The section sits between <!-- weekly-summary:start --> and
<!-- weekly-summary:end -->. With --weekly it only rewrites the section on
Sundays or when the current summary is a week old, so the workflow can call it
on every run and a missed Sunday run catches up the next time.
"""

import argparse
import csv
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta

from common import DATA_DIR, REPO_ROOT, log, sl_today

START, END = "<!-- weekly-summary:start -->", "<!-- weekly-summary:end -->"
DASHBOARD = "https://lanka-data-tracker-qmeq7gejtnaw6nyhu5jnoz.streamlit.app"


def load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(new, old):
    return (new / old - 1) * 100 if old else 0.0


def fmt_day(iso):
    return date.fromisoformat(iso[:10]).strftime("%a %-d %b")


def weather_lines(start, end):
    rows = [r for r in load("weather.csv") if start <= r["date"] <= end]
    if not rows:
        return []
    hot = max(rows, key=lambda r: float(r["temp_max_c"]))
    cool = min(rows, key=lambda r: float(r["temp_min_c"]))
    rain = defaultdict(float)
    for r in rows:
        rain[r["city"]] += float(r["precipitation_mm"])
    wet, dry = max(rain, key=rain.get), min(rain, key=rain.get)
    return [
        ("🌡️ Hottest", f"**{hot['city']}**, {float(hot['temp_max_c']):.1f} °C on {fmt_day(hot['date'])}"),
        ("🌙 Coolest night", f"**{cool['city']}**, {float(cool['temp_min_c']):.1f} °C on {fmt_day(cool['date'])}"),
        ("🌧️ Wettest", f"**{wet}**, {rain[wet]:.0f} mm over the week (driest: {dry}, {rain[dry]:.0f} mm)"),
    ]


def air_line():
    """Air quality uses its own last 7 days: snapshots run up to the present,
    while the daily datasets end yesterday."""
    rows = [r for r in load("air_quality.csv") if r["us_aqi"]]
    if not rows:
        return []
    since = (date.fromisoformat(max(r["time"] for r in rows)[:10]) - timedelta(days=6)).isoformat()
    rows = [r for r in rows if r["time"][:10] >= since]
    by_city = defaultdict(list)
    for r in rows:
        by_city[r["city"]].append(float(r["us_aqi"]))
    avg = {c: statistics.mean(v) for c, v in by_city.items()}
    worst, best = max(avg, key=avg.get), min(avg, key=avg.get)
    return [("🌫️ Air quality", f"Worst **{worst}** (average US AQI {avg[worst]:.0f}), "
                               f"cleanest {best} ({avg[best]:.0f})")]


def river_line(start, end):
    rows = load("river_discharge.csv")
    week = [r for r in rows if start <= r["date"] <= end]
    if not week:
        return []
    median = {}
    for river in {r["river"] for r in rows}:
        median[river] = statistics.median(float(r["discharge_m3s"]) for r in rows if r["river"] == river)
    peak = max(week, key=lambda r: float(r["discharge_m3s"]) / (median[r["river"]] or 1))
    ratio = float(peak["discharge_m3s"]) / (median[peak["river"]] or 1)
    return [("🏞️ Rivers", f"Highest relative flow: **{peak['river']}** at {float(peak['discharge_m3s']):.0f} m³/s "
                          f"on {fmt_day(peak['date'])} ({ratio:.1f}× its usual level)")]


def dengue_line():
    rows = load("dengue.csv")
    if not rows:
        return []
    weeks = sorted({(int(r["year"]), int(r["week"])) for r in rows})
    (y, w), prev = weeks[-1], weeks[-2] if len(weeks) > 1 else None
    this = [r for r in rows if (int(r["year"]), int(r["week"])) == (y, w)]
    total = sum(int(r["cases"]) for r in this)
    top = max(this, key=lambda r: int(r["cases"]))
    change = ""
    if prev:
        before = sum(int(r["cases"]) for r in rows if (int(r["year"]), int(r["week"])) == prev)
        change = f", {pct(total, before):+.0f}% on the week before"
    return [("🦟 Dengue", f"**{total:,} cases** in week {w} (latest report){change}; "
                         f"most in {top['district']} ({int(top['cases']):,})")]


def tourism_line():
    rows = load("tourism.csv")
    done = sorted(((int(r["year"]), int(r["month"])) for r in rows if r["complete"] == "true"), reverse=True)
    if not done:
        return []
    by_key = {(int(r["year"]), int(r["month"])): r for r in rows}
    y, m = done[0]
    last = int(by_key[(y, m)]["arrivals"])
    before = by_key.get((y - 1, m))
    vs = f" ({pct(last, int(before['arrivals'])):+.0f}% on {by_key[(y, m)]['month_name']} {y - 1})" if before else ""
    text = f"**{last:,}** visitors in {by_key[(y, m)]['month_name']} {y}{vs}"
    partial = [r for r in rows if r["complete"] == "false"]
    if partial:
        p = partial[0]
        text += f"; {int(p['arrivals']):,} so far in {p['month_name']} (to {fmt_day(p['as_of'])})"
    return [("✈️ Tourism", text)]


def latest_vs_week_ago(rows, value, end, key="date"):
    rows = sorted((r for r in rows if r[key][:10] <= end and r[value]), key=lambda r: r[key])
    if not rows:
        return None
    last = rows[-1]
    cutoff = (date.fromisoformat(last[key][:10]) - timedelta(days=7)).isoformat()
    older = [r for r in rows if r[key][:10] <= cutoff]
    return last, (older[-1] if older else None)


def economy_lines(start, end):
    lines = []
    fx = latest_vs_week_ago([r for r in load("exchange_rates.csv") if r["currency"] == "USD"],
                            "lkr_per_unit", end)
    if fx:
        last, old = fx
        move = f" ({pct(float(last['lkr_per_unit']), float(old['lkr_per_unit'])):+.2f}% in a week)" if old else ""
        lines.append(("💱 Rupee", f"**Rs {float(last['lkr_per_unit']):.2f}** per US$ on {fmt_day(last['date'])}{move}"))
    cse = latest_vs_week_ago(load("cse_market.csv"), "aspi", end)
    if cse:
        last, old = cse
        move = f", {pct(float(last['aspi']), float(old['aspi'])):+.1f}% in a week" if old else ""
        lines.append(("📈 ASPI", f"**{float(last['aspi']):,.0f}** on {fmt_day(last['date'])}{move}"))
    cbsl = sorted(load("cbsl_rates.csv"), key=lambda r: r["date"])
    if cbsl:
        r = cbsl[-1]
        lines.append(("🏦 Central Bank", f"Policy rate **{float(r['overnight_policy_rate_pct']):.2f}%**, "
                                         f"inflation {float(r['ccpi_inflation_pct']):.1f}% (CCPI)"))
    fuel = [r for r in load("fuel_prices.csv") if r["product_code"] == "LP 92"]
    if fuel:
        fuel.sort(key=lambda r: (r["date"], r["effective_time"]))
        last = fuel[-1]
        changed = start <= last["date"] <= end
        prev = fuel[-2]["price_lkr_per_litre"] if len(fuel) > 1 else None
        note = (f"**changed this week** to Rs {last['price_lkr_per_litre']} (from Rs {prev})" if changed
                else f"Rs {last['price_lkr_per_litre']}/L, unchanged since {fmt_day(last['date'])}")
        lines.append(("⛽ Petrol 92", note))
    return lines


def forecast_line():
    path = os.path.join(REPO_ROOT, "models", "metrics.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        m = json.load(f)
    live = {(r["target"], r["horizon_days"]): r["mae"] for r in m.get("live", [])}
    if ("temp_max_c", 1) in live:
        return [("🔮 Forecasts", f"Next-day max temperature off by **{live[('temp_max_c', 1)]:.1f} °C** "
                                 "on average over the last 30 days ([accuracy](FORECASTS.md))")]
    test = next((r for r in m["weather"] if (r["target"], r["horizon_days"]) == ("temp_max_c", 1)), None)
    return [("🔮 Forecasts", f"Next-day max temperature model: ±{test['model_mae']:.2f} °C on held-out data "
                             "([accuracy](FORECASTS.md))")] if test else []


def build(today):
    weather = load("weather.csv")
    end = max((r["date"] for r in weather), default=(today - timedelta(days=1)).isoformat())
    start = (date.fromisoformat(end) - timedelta(days=6)).isoformat()
    lines = (weather_lines(start, end) + air_line() + river_line(start, end)
             + dengue_line() + tourism_line() + economy_lines(start, end) + forecast_line())
    out = [START, f"## This week in Sri Lanka ({fmt_day(start)} – {fmt_day(end)})", "",
           f"*Generated {today.isoformat()} from the datasets below. "
           f"Explore it all on the [dashboard]({DASHBOARD}).*", "",
           "| | |", "|---|---|"]
    out += [f"| {topic} | {text} |" for topic, text in lines]
    return "\n".join(out + [END])


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--weekly", action="store_true",
                   help="only rewrite on Sundays or when the summary is a week old")
    args = p.parse_args()

    readme_path = os.path.join(REPO_ROOT, "README.md")
    with open(readme_path, encoding="utf-8") as f:
        readme = f.read()
    if START not in readme or END not in readme:
        log("Summary: markers not found in README.md")
        return 1
    today = sl_today()
    m = re.search(r"\*Generated (\d{4}-\d{2}-\d{2})", readme)
    if args.weekly and m:
        age = (today - date.fromisoformat(m.group(1))).days
        if not (age >= 7 or (today.weekday() == 6 and age > 0)):
            log(f"Summary: current one is from {m.group(1)}; nothing to do")
            return 0
    section = build(today)
    readme = readme[:readme.index(START)] + section + readme[readme.index(END) + len(END):]
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)
    log("Summary: README.md updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
