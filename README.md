# lanka-data-tracker

[![Data collection](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/daily-collect.yml/badge.svg)](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/daily-collect.yml)

An open, self-updating dataset of Sri Lankan data. A GitHub Actions workflow fetches
the latest values from free public APIs every morning (daily sources) and every 4 hours
(snapshots), appends them to CSV files in [`data/`](data/), and commits the result.
Nobody has to do anything by hand.

## Datasets

Cities: Wellawaya, Colombo, Kandy, Galle, Jaffna, Nuwara Eliya, Trincomalee.

| File | Contents | Frequency | Key | Source |
|---|---|---|---|---|
| [`data/weather.csv`](data/weather.csv) | Yesterday's max/min temperature (°C), precipitation sum (mm), max wind speed (km/h), mean humidity (%) per city | Daily | date + city | [Open-Meteo](https://open-meteo.com/) |
| [`data/exchange_rates.csv`](data/exchange_rates.csv) | LKR per 1 unit of USD, EUR, GBP, INR, JPY, AUD, CNY, AED | Daily | date + currency | [ExchangeRate-API open access](https://www.exchangerate-api.com/docs/free) |
| [`data/river_discharge.csv`](data/river_discharge.csv) | Yesterday's discharge (m³/s) of Kelani, Kalu, Mahaweli, Gin, Nilwala, Walawe, Deduru Oya, Kala Oya | Daily | date + river | [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) (GloFAS) |
| [`data/weather_snapshots.csv`](data/weather_snapshots.csv) | Current temperature, feels-like, humidity, precipitation, cloud cover, wind, UV index per city | Every 4 h | time + city | [Open-Meteo](https://open-meteo.com/) |
| [`data/air_quality.csv`](data/air_quality.csv) | US AQI, PM2.5, PM10, CO, NO₂, SO₂, O₃ (μg/m³) per city | Every 4 h | time + city | [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api) (CAMS) |
| [`data/marine.csv`](data/marine.csv) | Wave height/period/direction, swell height, sea surface temperature off Colombo, Kalpitiya, Jaffna, Trincomalee, Batticaloa, Hambantota, Galle | Every 4 h | time + location | [Open-Meteo Marine](https://open-meteo.com/en/docs/marine-weather-api) |
| [`data/earthquakes.csv`](data/earthquakes.csv) | M3.0+ earthquakes in the Sri Lanka / central Indian Ocean region (2°S–14°N, 72–90°E), with distance to Colombo | When events occur | USGS id | [USGS](https://earthquake.usgs.gov/fdsnws/event/1/) |

### Columns

**weather.csv**: `date, city, latitude, longitude, temp_max_c, temp_min_c, precipitation_mm, wind_speed_max_kmh, humidity_mean_pct`

- `date` is the Sri Lanka calendar day the values describe, always a complete
  day (the collector stores *yesterday*).

**exchange_rates.csv**: `date, currency, lkr_per_unit, source_updated_utc`

- `date` is the UTC date the provider last published its rates, so a stale
  response is never recorded under a newer date.
- `lkr_per_unit` is derived from USD-based rates: `rates[LKR] / rates[currency]`.

**river_discharge.csv**: `date, river, latitude, longitude, discharge_m3s`

- Modelled values (GloFAS) at a grid cell on each river's lower main channel, not
  gauge readings.

**weather_snapshots.csv / air_quality.csv / marine.csv**: `time, city|location, latitude, longitude, ...`

- `time` is the Sri Lanka local time of the observation as reported by the API
  (15-minute resolution for weather and marine, hourly for air quality).
- Air quality values are modelled (CAMS), not station measurements.

**earthquakes.csv**: `id, time_utc, time_local, magnitude, mag_type, depth_km, latitude, longitude, distance_to_colombo_km, place, url`

- Each run looks back 7 days, so a missed run never loses an event. Magnitudes are
  as first reported; USGS may revise them later.

All files are plain CSV with a header row. Load them directly, for example:

```python
import pandas as pd
url = "https://raw.githubusercontent.com/dhananjaya-hbc/lanka-data-tracker/main/data/weather.csv"
df = pd.read_csv(url, parse_dates=["date"])
```

## How the automation works

```
07:00 Sri Lanka (01:30 UTC), daily
    ├─ weather.py, exchange_rates.py, river_discharge.py, earthquakes.py
    └─ one commit per changed file ─► git pull --rebase ─► git push

01:00, 05:00, 09:00, 13:00, 17:00, 21:00 Sri Lanka, every 4 hours
    ├─ weather_snapshots.py, air_quality.py, marine.py, earthquakes.py
    └─ one commit per changed file ─► git pull --rebase ─► git push
```

Commit messages: `data: <source> update YYYY-MM-DD` for daily sources and
`data: <source> update YYYY-MM-DD HH:MM` (Sri Lanka time) for snapshots, e.g.
`data: air quality update 2026-10-06 09:00`.

- **Standard library only:** no `pip install`, so a run takes seconds.
- **Retries:** every HTTP request is retried 3 times with exponential backoff.
- **No duplicates:** every file is deduplicated on its key (see the table above),
  so re-running the workflow is always safe.
- **Independent sources:** if one source fails, the others still save and commit.
  The run is marked failed afterwards so the problem is visible.
- **One commit per source:** each changed CSV gets its own commit; files with no
  new rows get no commit.
- **Safe pushes:** a concurrency group prevents overlapping runs, and the job runs
  `git pull --rebase` before pushing.
- **Commit author:** taken from the repository variables `COMMIT_NAME` and
  `COMMIT_EMAIL`, falling back to `github-actions[bot]`.

The workflow can also be started manually from the Actions tab or with
`gh workflow run daily-collect.yml` (optionally `-f group=daily` or `-f group=snapshot`).

## Run locally

```bash
for c in weather exchange_rates river_discharge weather_snapshots air_quality marine earthquakes; do
  python3 collectors/$c.py
done
```

Requires Python 3.9+. No dependencies.

## Project structure

```
collectors/
  common.py             shared helpers: HTTP with retries, CSV dedupe/append,
                        Open-Meteo snapshots, city list, Sri Lanka date
  weather.py            daily weather
  exchange_rates.py     exchange rates
  river_discharge.py    river discharge
  weather_snapshots.py  4-hourly weather
  air_quality.py        4-hourly air quality
  marine.py             4-hourly sea conditions
  earthquakes.py        earthquakes
data/                   the datasets (CSV), append-only
.github/workflows/
  daily-collect.yml   scheduled workflow
```

## Roadmap

- [ ] **Validation:** schema and range checks (e.g. temperature bounds, positive
      rates, no gaps in dates) that run before every commit, plus a data-quality report.
- [ ] **Streamlit dashboard:** interactive charts of weather trends per city and
      LKR exchange-rate history.
- [ ] **Forecasting models:** next-day temperature/rainfall and exchange-rate
      forecasts, with a weekly workflow that automatically retrains the models on the
      latest data and publishes metrics.
- [ ] More sources: fuel prices, CSE market indices, CBSL policy rates.

## Data licensing

Weather, air quality, marine and flood data © Open-Meteo, licensed under
[CC BY 4.0](https://open-meteo.com/en/license) (air quality: Copernicus CAMS; river
discharge: Copernicus GloFAS). Earthquake data from the U.S. Geological Survey (public
domain). Exchange rates from [ExchangeRate-API](https://www.exchangerate-api.com) (attribution
required by their [terms](https://www.exchangerate-api.com/terms)).
