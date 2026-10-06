"""Lanka Data Tracker dashboard (Streamlit).

Reads the CSVs in ../data, so it always shows whatever the data workflow last
committed. Run locally with:

    pip install -r dashboard/requirements.txt
    streamlit run dashboard/app.py
"""

import json
import os
from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# Validated reference palette (dataviz skill): first three categorical slots,
# which pass all-pairs CVD checks in both modes, plus a one-hue blue ramp.
PALETTES = {
    "light": {"series": ["#2a78d6", "#eb6834", "#1baf7a"], "muted": "#898781",
              "surface": "#fcfcfb", "seq": ["#cde2fb", "#0d366b"]},
    "dark": {"series": ["#3987e5", "#d95926", "#199e70"], "muted": "#898781",
             "surface": "#1a1a19", "seq": ["#104281", "#b7d3f6"]},
}
MAX_SERIES = 3

st.set_page_config(page_title="Lanka Data Tracker", page_icon="🇱🇰", layout="wide")


def pal():
    try:
        mode = st.context.theme.type or "light"
    except AttributeError:
        mode = "light"
    return PALETTES.get(mode, PALETTES["light"])


@st.cache_data(ttl=900)
def load(name, dates=()):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    for col in dates:
        df[col] = pd.to_datetime(df[col])
    return df


# --- chart helpers ----------------------------------------------------------

def esc(field):
    """Escape characters Vega-Lite treats specially in field names."""
    return field.replace(".", "\\.").replace("[", "\\[").replace("]", "\\]")


def series_scale(key, selected):
    """Color follows the entity: each selected item keeps its slot while it
    stays selected, so adding/removing another never repaints it."""
    slots = st.session_state.setdefault(f"colors_{key}", {})
    for name in list(slots):
        if name not in selected:
            del slots[name]
    for name in selected:
        if name not in slots:
            slots[name] = min(set(range(MAX_SERIES)) - set(slots.values()))
    colors = pal()["series"]
    return alt.Scale(domain=list(selected), range=[colors[slots[n]] for n in selected])


def line_chart(df, x, y, y_title, series=None, scale=None, fmt=",.1f",
               interpolate="linear", height=300):
    """Line chart with a crosshair: hovering shows every series' value at that x."""
    p = pal()
    base = alt.Chart(df).encode(x=alt.X(f"{x}:T", title=None))
    color = (alt.Color(f"{series}:N", scale=scale, legend=alt.Legend(title=None, orient="top"))
             if series else alt.value(p["series"][0]))
    lines = base.mark_line(strokeWidth=2, interpolate=interpolate).encode(
        y=alt.Y(f"{y}:Q", title=y_title), color=color)
    hover = alt.selection_point(fields=[x], nearest=True, on="pointerover",
                                empty=False, clear="pointerout")
    points = base.mark_point(filled=True, size=64, stroke=p["surface"], strokeWidth=2).encode(
        y=f"{y}:Q", color=color,
        opacity=alt.condition(hover, alt.value(1), alt.value(0)))
    if series:
        names = list(scale.domain) if scale is not None else sorted(df[series].unique())
        rule_src = alt.Chart(df).transform_pivot(series, value=y, groupby=[x])
        tips = [alt.Tooltip(f"{x}:T", title="Date")] + [
            alt.Tooltip(f"{esc(n)}:Q", title=n, format=fmt) for n in names]
    else:
        rule_src = alt.Chart(df)
        tips = [alt.Tooltip(f"{x}:T", title="Date"), alt.Tooltip(f"{y}:Q", title=y_title, format=fmt)]
    rule = rule_src.mark_rule(color=p["muted"], strokeWidth=1).encode(
        x=f"{x}:T", opacity=alt.condition(hover, alt.value(0.7), alt.value(0)),
        tooltip=tips).add_params(hover)
    return (lines + points + rule).properties(height=height)


def bar_chart(df, x, y, x_title, y_title, tips, horizontal=False, sort=None, height=300):
    """Single-series bars: one color, 4px rounded data ends, 2px gaps."""
    color = pal()["series"][0]
    if horizontal:
        enc = dict(y=alt.Y(f"{x}:N", title=x_title, sort=sort or "-x"),
                   x=alt.X(f"{y}:Q", title=y_title))
    else:
        enc = dict(x=alt.X(f"{x}:O", title=x_title, sort=sort),
                   y=alt.Y(f"{y}:Q", title=y_title))
    return (alt.Chart(df).mark_bar(color=color, cornerRadiusEnd=4)
            .encode(**enc, tooltip=tips)
            .configure_scale(bandPaddingInner=0.3)
            .properties(height=height))


def show(chart, data, label="Show data"):
    st.altair_chart(chart, width="stretch")
    with st.expander(label):
        st.dataframe(data, width="stretch", hide_index=True)


def since(df, col, choice):
    days = {"Last 30 days": 30, "Last 90 days": 90, "Last year": 365, "Last 3 years": 1095}
    if choice not in days or df.empty:
        return df
    return df[df[col] >= df[col].max() - timedelta(days=days[choice])]


RANGES = ["Last 30 days", "Last 90 days", "Last year", "Last 3 years", "All"]


def delta(series):
    return series.iloc[-1] - series.iloc[-2] if len(series) > 1 else None


# --- page -------------------------------------------------------------------

st.title("🇱🇰 Lanka Data Tracker")
st.caption("An open, self-updating dataset of Sri Lanka, collected automatically "
           "every day by GitHub Actions. Hover any chart for values; open "
           "**Show data** under a chart for the table.")

weather = load("weather.csv", ("date",))
solar = load("solar.csv", ("date",))
snaps = load("weather_snapshots.csv", ("time",))
air = load("air_quality.csv", ("time",))
marine = load("marine.csv", ("time",))
rivers = load("river_discharge.csv", ("date",))
dengue = load("dengue.csv", ("week_start",))
fx = load("exchange_rates.csv", ("date",))
fuel = load("fuel_prices.csv", ("date",))
cse = load("cse_market.csv", ("date",))
cbsl = load("cbsl_rates.csv", ("date",))
wb = load("economy_indicators.csv")
fc_weather = load("forecasts_weather.csv", ("target_date", "based_on_date"))
fc_dengue = load("forecasts_dengue.csv", ("week_start",))
METRICS = os.path.join(DATA, "..", "models", "metrics.json")
metrics = json.load(open(METRICS)) if os.path.exists(METRICS) else None

tabs = st.tabs(["Overview", "Weather", "Dengue", "Air & sea", "Rivers", "Economy", "Forecasts"])

# Overview -------------------------------------------------------------------
with tabs[0]:
    cols = st.columns(5)
    if not fx.empty:
        usd = fx[fx.currency == "USD"].sort_values("date")
        cols[0].metric("LKR per US$", f"{usd.lkr_per_unit.iloc[-1]:.2f}",
                       None if delta(usd.lkr_per_unit) is None else f"{delta(usd.lkr_per_unit):+.2f}",
                       delta_color="inverse", help=f"As of {usd.date.iloc[-1]:%d %b %Y}")
    if not cse.empty:
        last = cse.sort_values("date").iloc[-1]
        cols[1].metric("ASPI", f"{last.aspi:,.0f}", f"{last.aspi_change:+,.1f} ({last.aspi_change_pct:+.2f}%)",
                       help=f"Colombo Stock Exchange, {last.date:%d %b %Y}")
    if not fuel.empty:
        p92 = fuel[fuel.product_code == "LP 92"].sort_values(["date", "effective_time"])
        cols[2].metric("Petrol 92 (Rs/L)", f"{p92.price_lkr_per_litre.iloc[-1]:,.0f}",
                       None if delta(p92.price_lkr_per_litre) is None
                       else f"{delta(p92.price_lkr_per_litre):+,.0f}",
                       delta_color="inverse", help=f"Since {p92.date.iloc[-1]:%d %b %Y}")
    if not dengue.empty:
        weekly = dengue.groupby(["year", "week"]).cases.sum()
        y, w = weekly.index[-1]
        cols[3].metric("Dengue cases (week)", f"{weekly.iloc[-1]:,}",
                       None if delta(weekly) is None else f"{delta(weekly):+,}",
                       delta_color="inverse", help=f"{y} week {w}, all districts")
    if not cbsl.empty:
        last = cbsl.sort_values("date").iloc[-1]
        cols[4].metric("Inflation (CCPI)", f"{last.ccpi_inflation_pct:.1f}%",
                       help=f"Overnight Policy Rate {last.overnight_policy_rate_pct:.2f}%")
    elif not wb.empty:
        infl = wb[wb.indicator_id == "FP.CPI.TOTL.ZG"].sort_values("year")
        cols[4].metric("Inflation (annual)", f"{infl.value.iloc[-1]:.1f}%",
                       help=f"World Bank, {infl.year.iloc[-1]}")

    st.subheader("Right now across Sri Lanka")
    if not snaps.empty:
        now = snaps.sort_values("time").groupby("city").tail(1)
        table = now[["city", "time", "temp_c", "feels_like_c", "humidity_pct",
                     "precipitation_mm", "uv_index"]]
        if not air.empty:
            aq = air.sort_values("time").groupby("city").tail(1)[["city", "us_aqi", "pm2_5"]]
            table = table.merge(aq, on="city", how="left")
            bands = [(50, "Good"), (100, "Moderate"), (150, "Unhealthy for sensitive groups"),
                     (200, "Unhealthy"), (300, "Very unhealthy"), (10**6, "Hazardous")]
            table["air"] = table.us_aqi.map(
                lambda v: next(label for limit, label in bands if v <= limit) if pd.notna(v) else "")
        st.dataframe(
            table.sort_values("city"), hide_index=True, width="stretch",
            column_config={
                "city": "City", "time": st.column_config.DatetimeColumn("Observed", format="D MMM, HH:mm"),
                "temp_c": st.column_config.NumberColumn("Temp °C", format="%.1f"),
                "feels_like_c": st.column_config.NumberColumn("Feels like °C", format="%.1f"),
                "humidity_pct": st.column_config.NumberColumn("Humidity %"),
                "precipitation_mm": st.column_config.NumberColumn("Rain mm", format="%.1f"),
                "uv_index": st.column_config.NumberColumn("UV", format="%.1f"),
                "us_aqi": st.column_config.NumberColumn("US AQI"),
                "pm2_5": st.column_config.NumberColumn("PM2.5 μg/m³", format="%.1f"),
                "air": "Air quality",
            })

# Weather --------------------------------------------------------------------
with tabs[1]:
    c1, c2 = st.columns([3, 1])
    cities = c1.multiselect("Cities (up to 3)", sorted(weather.city.unique()) if not weather.empty else [],
                            default=["Colombo", "Kandy", "Nuwara Eliya"], max_selections=MAX_SERIES,
                            key="w_cities")
    rng = c2.selectbox("Period", RANGES, index=2, key="w_range")
    if cities and not weather.empty:
        scale = series_scale("cities", cities)
        w = since(weather[weather.city.isin(cities)], "date", rng)
        st.subheader("Daily maximum temperature")
        show(line_chart(w, "date", "temp_max_c", "°C", "city", scale), w)
        st.subheader("Weekly rainfall")
        wk = (w.set_index("date").groupby("city").precipitation_mm.resample("W-SUN").sum()
              .reset_index())
        show(line_chart(wk, "date", "precipitation_mm", "mm per week", "city", scale), wk)
        if not solar.empty:
            st.subheader("Solar radiation (30-day average)")
            s = since(solar[solar.city.isin(cities)], "date", rng).sort_values("date")
            s["radiation_30d"] = s.groupby("city").radiation_kwh_m2.transform(
                lambda v: v.rolling(30, min_periods=7).mean())
            show(line_chart(s, "date", "radiation_30d", "kWh/m² per day", "city", scale, fmt=".2f"), s)

# Dengue ---------------------------------------------------------------------
with tabs[2]:
    if dengue.empty:
        st.info("No dengue data yet.")
    else:
        year = dengue.year.max()
        d = dengue[dengue.year == year]
        st.subheader(f"Weekly dengue cases by district, {year}")
        p = pal()
        order = d.groupby("district").cases.sum().sort_values(ascending=False).index.tolist()
        heat = (alt.Chart(d).mark_rect(stroke=p["surface"], strokeWidth=2)
                .encode(x=alt.X("week:O", title="Week"),
                        y=alt.Y("district:N", sort=order, title=None),
                        color=alt.Color("cases:Q", title="Cases", scale=alt.Scale(range=p["seq"])),
                        tooltip=["district", "week", alt.Tooltip("week_start:T", title="Week starting"),
                                 alt.Tooltip("cases:Q", format=",")])
                .properties(height=26 * len(order)))
        show(heat, d.pivot_table(index="district", columns="week", values="cases")
                   .rename(columns=lambda c: f"W{c}").reset_index())

        district = st.selectbox("District", order, key="d_district")
        dd = d[d.district == district]
        st.subheader(f"{district}: cases and rainfall by week")
        st.caption("Two separate charts on the same weeks. Heavy rain typically "
                   "precedes a rise in dengue cases by a few weeks.")
        show(bar_chart(dd, "week", "cases", "Week", "Dengue cases",
                       ["week", alt.Tooltip("week_start:T", title="Week starting"),
                        alt.Tooltip("cases:Q", format=",")], height=220), dd)
        if district in set(weather.city):
            rain = weather[(weather.city == district) & (weather.date.dt.year == year)].copy()
            iso = rain.date.dt.isocalendar()
            rain = (rain.assign(week=iso.week.astype(int), iso_year=iso.year.astype(int))
                    .query("iso_year == @year").groupby("week").precipitation_mm.sum().reset_index())
            rain = rain[rain.week <= dd.week.max()]
            show(bar_chart(rain, "week", "precipitation_mm", "Week", "Rainfall (mm)",
                           ["week", alt.Tooltip("precipitation_mm:Q", title="Rain (mm)", format=".1f")],
                           height=220), rain, "Show rainfall data")

# Air & sea ------------------------------------------------------------------
with tabs[3]:
    if not air.empty:
        latest = air.sort_values("time").groupby("city").tail(1)
        st.subheader(f"Air quality now (US AQI, {latest.time.max():%d %b %H:%M})")
        show(bar_chart(latest, "city", "us_aqi", None, "US AQI (higher is worse)",
                       ["city", "us_aqi", alt.Tooltip("pm2_5:Q", title="PM2.5"), "time"],
                       horizontal=True, height=22 * len(latest)), latest)
        aq_cities = st.multiselect("Cities (up to 3)", sorted(air.city.unique()),
                                   default=["Colombo", "Kandy", "Jaffna"], max_selections=MAX_SERIES,
                                   key="a_cities")
        if aq_cities:
            a = air[air.city.isin(aq_cities)]
            st.subheader("US AQI over time")
            show(line_chart(a, "time", "us_aqi", "US AQI", "city", series_scale("aq", aq_cities),
                            fmt=".0f"), a)
    if not marine.empty:
        spots = st.multiselect("Coastal points (up to 3)", sorted(marine.location.unique()),
                               default=["Colombo", "Galle", "Trincomalee"], max_selections=MAX_SERIES,
                               key="m_spots")
        if spots:
            m = marine[marine.location.isin(spots)]
            st.subheader("Wave height")
            show(line_chart(m, "time", "wave_height_m", "metres", "location",
                            series_scale("marine", spots), fmt=".2f"), m)

# Rivers ---------------------------------------------------------------------
with tabs[4]:
    if not rivers.empty:
        c1, c2 = st.columns([3, 1])
        names = c1.multiselect("Rivers (up to 3)", sorted(rivers.river.unique()),
                               default=["Kelani Ganga", "Kalu Ganga", "Mahaweli Ganga"],
                               max_selections=MAX_SERIES, key="r_names")
        rng = c2.selectbox("Period", RANGES, index=2, key="r_range")
        if names:
            r = since(rivers[rivers.river.isin(names)], "date", rng)
            st.subheader("River discharge")
            st.caption("Modelled daily flow (GloFAS). Spikes mark flood events.")
            show(line_chart(r, "date", "discharge_m3s", "m³/s", "river",
                            series_scale("rivers", names)), r)

# Economy --------------------------------------------------------------------
with tabs[5]:
    if not fx.empty:
        cur = st.selectbox("Currency", sorted(fx.currency.unique()),
                           index=sorted(fx.currency.unique()).index("USD"), key="e_cur")
        f = fx[fx.currency == cur]
        st.subheader(f"Sri Lankan rupees per 1 {cur}")
        show(line_chart(f, "date", "lkr_per_unit", "LKR", fmt=",.3f"), f)
    if not fuel.empty:
        products = sorted(fuel["product"].unique())
        c1, c2 = st.columns([3, 1])
        chosen = c1.multiselect("Fuel products (up to 3)", products, max_selections=MAX_SERIES,
                                default=["Lanka Petrol 92 Octane", "Lanka Auto Diesel", "Lanka Kerosene"],
                                key="e_fuel")
        rng = c2.selectbox("Period", RANGES, index=4, key="e_range")
        if chosen:
            fp = since(fuel[fuel["product"].isin(chosen)], "date", rng)
            st.subheader("Retail fuel prices (Rs per litre)")
            st.caption("Each step is a price revision by Ceylon Petroleum Corporation.")
            show(line_chart(fp, "date", "price_lkr_per_litre", "Rs per litre", "product",
                            series_scale("fuel", chosen), fmt=",.2f", interpolate="step-after"), fp)
    if not cse.empty:
        st.subheader("All Share Price Index (ASPI)")
        show(line_chart(cse, "date", "aspi", "ASPI", fmt=",.2f"), cse)
    if not wb.empty:
        labels = wb.drop_duplicates("indicator_id").set_index("indicator")["indicator_id"]
        name = st.selectbox("World Bank indicator", sorted(labels.index),
                            index=sorted(labels.index).index("GDP growth (annual %)"), key="e_wb")
        ind = wb[wb.indicator == name].sort_values("year")
        st.subheader(name)
        show(bar_chart(ind, "year", "value", None, None,
                       ["year", alt.Tooltip("value:Q", format=",.2f")], height=280), ind)

# Forecasts -----------------------------------------------------------------
with tabs[6]:
    if fc_weather.empty or metrics is None:
        st.info("No forecasts yet. They appear after the first forecast workflow run.")
    else:
        st.caption(f"Machine-learning forecasts, retrained weekly (last: {metrics['trained_at'][:10]}). "
                   "See FORECASTS.md in the repository for how accurate each model is.")
        latest = fc_weather[fc_weather.based_on_date == fc_weather.based_on_date.max()]
        st.subheader(f"Weather forecast for {', '.join(sorted(latest.target_date.dt.strftime('%a %d %b').unique()))}")
        st.dataframe(
            latest.sort_values(["city", "horizon_days"]), hide_index=True, width="stretch",
            column_order=["city", "target_date", "temp_max_c", "temp_min_c", "precipitation_mm"],
            column_config={
                "city": "City", "target_date": st.column_config.DateColumn("Date", format="ddd D MMM"),
                "temp_max_c": st.column_config.NumberColumn("Max °C", format="%.1f"),
                "temp_min_c": st.column_config.NumberColumn("Min °C", format="%.1f"),
                "precipitation_mm": st.column_config.NumberColumn("Rain mm", format="%.1f")})

        city = st.selectbox("Forecast vs actual for", sorted(fc_weather.city.unique()),
                            index=sorted(fc_weather.city.unique()).index("Colombo"), key="f_city")
        f1 = fc_weather[(fc_weather.city == city) & (fc_weather.horizon_days == 1)]
        actual = weather[(weather.city == city) & (weather.date >= f1.target_date.min())]
        both = pd.concat([
            actual.assign(series="Actual")[["date", "series", "temp_max_c"]],
            f1.rename(columns={"target_date": "date"}).assign(series="Forecast (1 day ahead)")
              [["date", "series", "temp_max_c"]]])
        scale = alt.Scale(domain=["Actual", "Forecast (1 day ahead)"], range=pal()["series"][:2])
        st.subheader(f"{city}: maximum temperature, forecast vs actual")
        show(line_chart(both, "date", "temp_max_c", "°C", "series", scale), both)

        if not fc_dengue.empty:
            nxt = fc_dengue[fc_dengue.week_start == fc_dengue.week_start.max()]
            wk = nxt.iloc[0]
            st.subheader(f"Dengue cases forecast, week {wk.week} ({wk.week_start:%d %b})")
            st.caption("Experimental: only this year's weekly reports are available for training so far.")
            show(bar_chart(nxt, "district", "cases_pred", None, "Predicted cases",
                           ["district", alt.Tooltip("cases_pred:Q", title="Predicted cases")],
                           horizontal=True, height=22 * len(nxt)), nxt)

        st.subheader("Model accuracy on held-out data")
        acc = pd.DataFrame(metrics["weather"])
        acc = pd.concat([acc, pd.DataFrame([{**metrics["dengue"], "horizon_days": 7}])], ignore_index=True)
        st.dataframe(acc, hide_index=True, width="stretch",
                     column_order=["target", "horizon_days", "model_mae", "persistence_mae",
                                   "climatology_mae", "skill_vs_best_baseline"],
                     column_config={
                         "target": "Target", "horizon_days": "Days ahead",
                         "model_mae": st.column_config.NumberColumn("Model error (MAE)", format="%.2f"),
                         "persistence_mae": st.column_config.NumberColumn("“Same as today” error", format="%.2f"),
                         "climatology_mae": st.column_config.NumberColumn("“Usual for the month” error", format="%.2f"),
                         "skill_vs_best_baseline": st.column_config.NumberColumn(
                             "Improvement vs best baseline", format="percent")})

st.divider()
st.caption("Sources: Open-Meteo (CC BY 4.0), ExchangeRate-API, USGS, National Dengue "
           "Control Unit, Ceylon Petroleum Corporation, Central Bank of Sri Lanka, "
           "Colombo Stock Exchange, World Bank (CC BY 4.0). Data health: STATUS.md in the repository.")
