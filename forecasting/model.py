"""Shared feature building for the forecasting models."""

import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
MODELS = os.path.join(ROOT, "models")

WEATHER_VARS = ["temp_max_c", "temp_min_c", "precipitation_mm",
                "wind_speed_max_kmh", "humidity_mean_pct"]
WEATHER_TARGETS = ["temp_max_c", "temp_min_c", "precipitation_mm"]
HORIZONS = [1, 2]          # days after the last observed day
LAGS = 7                   # days of history per feature
RAIN_WEEKS = 6             # weeks of rainfall history for dengue
CASE_LAGS = 4              # weeks of case history for dengue
# Kalmunai RDHS has no city of its own in weather.csv; it lies in Ampara district.
RAIN_CITY = {"Kalmunai": "Ampara"}


def load(name, dates=()):
    df = pd.read_csv(os.path.join(DATA, name))
    for col in dates:
        df[col] = pd.to_datetime(df[col])
    return df


def season(index_values, period):
    angle = 2 * np.pi * np.asarray(index_values, dtype=float) / period
    return np.sin(angle), np.cos(angle)


def weather_features(weather, cities=None):
    """One row per (city, date) with lagged weather, seasonality and the
    future targets y_<var>_h<h> (NaN where the future isn't known yet)."""
    cities = cities or sorted(weather.city.unique())
    frames = []
    for city, g in weather.sort_values("date").groupby("city"):
        g = g.set_index("date")[WEATHER_VARS].asfreq("D")
        f = pd.DataFrame(index=g.index)
        for v in WEATHER_VARS:
            for lag in range(LAGS):
                f[f"{v}_lag{lag}"] = g[v].shift(lag)
        f["rain_7d"] = g["precipitation_mm"].rolling(7).sum()
        f["rain_30d"] = g["precipitation_mm"].rolling(30, min_periods=20).sum()
        for h in HORIZONS:
            # day-of-year of the *target* day, so each horizon sees its own season
            f[f"doy_sin_h{h}"], f[f"doy_cos_h{h}"] = season((g.index + pd.Timedelta(days=h)).dayofyear, 365.25)
            for t in WEATHER_TARGETS:
                f[f"y_{t}_h{h}"] = g[t].shift(-h)
        f["city"] = city
        frames.append(f.reset_index())
    df = pd.concat(frames, ignore_index=True)
    df["city"] = pd.Categorical(df["city"], categories=cities)
    return df


def weather_columns(h):
    lagged = [f"{v}_lag{lag}" for v in WEATHER_VARS for lag in range(LAGS)]
    return lagged + ["rain_7d", "rain_30d", f"doy_sin_h{h}", f"doy_cos_h{h}", "city"]


def weekly_rain(weather):
    iso = weather.date.dt.isocalendar()
    return (weather.assign(year=iso.year.astype(int), week=iso.week.astype(int))
            .groupby(["city", "year", "week"]).precipitation_mm.sum()
            .rename("rain_mm").reset_index())


def dengue_features(dengue, weather, districts=None):
    """One row per (district, week) with lagged cases and rainfall,
    seasonality, and the target y_cases_next (next week's cases)."""
    districts = districts or sorted(dengue.district.unique())
    rain = weekly_rain(weather)
    frames = []
    for district, g in dengue.sort_values(["year", "week"]).groupby("district"):
        g = g.reset_index(drop=True)
        r = rain[rain.city == RAIN_CITY.get(district, district)]
        g = g.merge(r[["year", "week", "rain_mm"]], on=["year", "week"], how="left")
        f = g[["year", "week", "week_start"]].copy()
        for lag in range(CASE_LAGS):
            f[f"cases_lag{lag}"] = g.cases.shift(lag)
        for lag in range(RAIN_WEEKS):
            f[f"rain_lag{lag}"] = g.rain_mm.shift(lag)
        f["week_sin"], f["week_cos"] = season(g.week + 1, 52.18)
        f["y_cases_next"] = g.cases.shift(-1)
        f["district"] = district
        frames.append(f)
    df = pd.concat(frames, ignore_index=True)
    df["district"] = pd.Categorical(df["district"], categories=districts)
    return df


def dengue_columns():
    return ([f"cases_lag{i}" for i in range(CASE_LAGS)]
            + [f"rain_lag{i}" for i in range(RAIN_WEEKS)]
            + ["week_sin", "week_cos", "district"])
