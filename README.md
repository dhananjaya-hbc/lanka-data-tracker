# lanka-data-tracker

[![Data collection](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/daily-collect.yml/badge.svg)](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/daily-collect.yml)
[![Tests](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/tests.yml)
[![Open the dashboard](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://lanka-data-tracker-qmeq7gejtnaw6nyhu5jnoz.streamlit.app)

An open, self-updating dataset of Sri Lankan data. A GitHub Actions workflow fetches
the latest values from free public APIs every morning (daily sources) and every 4 hours
(snapshots), and appends them to CSV files in [`data/`](data/).
Nobody has to do anything by hand.

**Live dashboard:** [lanka-data-tracker-qmeq7gejtnaw6nyhu5jnoz.streamlit.app](https://lanka-data-tracker-qmeq7gejtnaw6nyhu5jnoz.streamlit.app)

**Data health:** see [`STATUS.md`](STATUS.md) for every dataset's latest data and
whether it is up to date.

<!-- weekly-summary:start -->
## This week in Sri Lanka (Tue 29 Sep – Mon 5 Oct)

*Generated 2026-10-07 from the datasets below. Explore it all on the [dashboard](https://lanka-data-tracker-qmeq7gejtnaw6nyhu5jnoz.streamlit.app).*

| | |
|---|---|
| 🌡️ Hottest | **Kilinochchi**, 36.6 °C on Thu 1 Oct |
| 🌙 Coolest night | **Nuwara Eliya**, 12.6 °C on Sat 3 Oct |
| 🌧️ Wettest | **Kurunegala**, 88 mm over the week (driest: Mullaitivu, 7 mm) |
| 🌫️ Air quality | Worst **Gampaha** (average US AQI 83), cleanest Kilinochchi (35) |
| 🏞️ Rivers | Highest relative flow: **Gin Ganga** at 49 m³/s on Tue 29 Sep (1.4× its usual level) |
| 🦟 Dengue | **1,156 cases** in week 37 (latest report), +0% on the week before; most in Gampaha (218) |
| 💱 Rupee | **Rs 330.68** per US$ on Mon 5 Oct |
| 📈 ASPI | **20,644** on Mon 5 Oct |
| 🏦 Central Bank | Policy rate **8.75%**, inflation 8.0% (CCPI) |
| ⛽ Petrol 92 | **changed this week** to Rs 414 (from Rs 399) |
| 🔮 Forecasts | Next-day max temperature model: ±0.82 °C on held-out data ([accuracy](FORECASTS.md)) |
<!-- weekly-summary:end -->

## Datasets

Cities (26): all 25 district capitals (Colombo, Gampaha, Kalutara, Kandy, Matale,
Nuwara Eliya, Galle, Matara, Hambantota, Jaffna, Kilinochchi, Mannar, Vavuniya,
Mullaitivu, Batticaloa, Ampara, Trincomalee, Kurunegala, Puttalam, Anuradhapura,
Polonnaruwa, Badulla, Monaragala, Ratnapura, Kegalle) plus Wellawaya. City names
match the `district` column in `dengue.csv`, so the datasets join directly.

| File | Contents | Frequency | Key | Source |
|---|---|---|---|---|
| [`data/weather.csv`](data/weather.csv) | Yesterday's max/min temperature (°C), precipitation sum (mm), max wind speed (km/h), mean humidity (%) per city | Daily | date + city | [Open-Meteo](https://open-meteo.com/) |
| [`data/exchange_rates.csv`](data/exchange_rates.csv) | LKR per 1 unit of USD, EUR, GBP, INR, JPY, AUD, CNY, AED | Daily | date + currency | [ExchangeRate-API open access](https://www.exchangerate-api.com/docs/free) |
| [`data/river_discharge.csv`](data/river_discharge.csv) | Yesterday's discharge (m³/s) of Kelani, Kalu, Mahaweli, Gin, Nilwala, Walawe, Deduru Oya, Kala Oya | Daily | date + river | [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) (GloFAS) |
| [`data/weather_snapshots.csv`](data/weather_snapshots.csv) | Current temperature, feels-like, humidity, precipitation, cloud cover, wind, UV index per city | Every 4 h | time + city | [Open-Meteo](https://open-meteo.com/) |
| [`data/air_quality.csv`](data/air_quality.csv) | US AQI, PM2.5, PM10, CO, NO₂, SO₂, O₃ (μg/m³) per city | Every 4 h | time + city | [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api) (CAMS) |
| [`data/marine.csv`](data/marine.csv) | Wave height/period/direction, swell height, sea surface temperature off Colombo, Kalpitiya, Jaffna, Trincomalee, Batticaloa, Hambantota, Galle | Every 4 h | time + location | [Open-Meteo Marine](https://open-meteo.com/en/docs/marine-weather-api) |
| [`data/solar.csv`](data/solar.csv) | Yesterday's solar radiation (kWh/m²), sunshine hours, daylight hours, max UV index per city | Daily | date + city | [Open-Meteo](https://open-meteo.com/) |
| [`data/dengue.csv`](data/dengue.csv) | Weekly dengue cases and year-to-date total for all 25 districts (Ampara split into Ampara and Kalmunai RDHS) | Weekly (checked daily) | year + week + district | [National Dengue Control Unit](https://www.dengue.health.gov.lk/weekly-report/) weekly reports |
| [`data/fuel_prices.csv`](data/fuel_prices.csv) | Retail price (LKR/litre) of petrol 92/95, auto/super diesel, kerosene, industrial kerosene, furnace oils; full history since 1990 | Each price revision (checked daily) | date + effective_time + product | [Ceylon Petroleum Corporation](https://ceypetco.gov.lk/historical-prices/) |
| [`data/economy_indicators.csv`](data/economy_indicators.csv) | GDP, GDP growth, GDP per capita, inflation, unemployment, current account, exports, imports, remittances, tourist arrivals, reserves, LKR/USD, population | Annual (checked daily) | year + indicator_id | [World Bank API](https://data.worldbank.org/country/sri-lanka) |
| [`data/cbsl_rates.csv`](data/cbsl_rates.csv) | CCPI headline inflation, Overnight Policy Rate, USD/LKR TT buy and sell rates | Weekdays | date | [Central Bank of Sri Lanka](https://www.cbsl.gov.lk/) |
| [`data/cse_market.csv`](data/cse_market.csv) | ASPI and S&P SL20 index close and change, turnover (LKR), share volume, number of trades | Trading days | date | [Colombo Stock Exchange](https://www.cse.lk/) |
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

**solar.csv**: `date, city, latitude, longitude, radiation_kwh_m2, sunshine_hours, daylight_hours, uv_index_max`

- `radiation_kwh_m2` is the day's total shortwave (global horizontal) radiation,
  the main input for solar PV yield estimates.

**dengue.csv**: `year, week, week_start, week_end, district, cases, cumulative_cases, source_report_week`

- Weeks run Monday–Sunday (ISO weeks). `cases` is as first published; later
  reports may revise a week slightly.
- Every report is checked: the district counts must add up to the report's total.
- When a report's table is an image, the week is filled from the next week's
  report (which repeats the previous week); `source_report_week` shows this.

**fuel_prices.csv**: `date, effective_time, product_code, product, price_lkr_per_litre`

- One row per product per price revision. `effective_time` is only set when CPC
  changed prices twice on one day (e.g. 17 Oct 2022).

**economy_indicators.csv**: `year, indicator_id, indicator, value`

- World Bank revises past figures; rows are updated in place when that happens,
  so the latest published figure is always shown.

**cbsl_rates.csv**: `date, ccpi_inflation_pct, overnight_policy_rate_pct, usd_tt_buy, usd_tt_sell`

- As shown on the CBSL website on that weekday (TT rates are quoted at 9:30 a.m.;
  recorded from 13:00 Sri Lanka time). Public holidays repeat the last business day.

**cse_market.csv**: `date, aspi, aspi_change, aspi_change_pct, sp_sl20, sp_sl20_change, sp_sl20_change_pct, turnover_lkr, share_volume, trades`

- Taken from the JSON endpoints behind cse.lk (unofficial). Runs during trading
  hours store intraday values; later runs overwrite them, so each row ends at the close.

### History

`weather.csv`, `solar.csv` and `river_discharge.csv` were backfilled from
**1 January 2020** with [`collectors/backfill.py`](collectors/backfill.py) (Open-Meteo
archive and GloFAS), so they hold years of history, not just days. Backfilled solar
rows have a blank `uv_index_max` (not available in the archive). Dengue (all of the
current year) and fuel prices (since 1990) backfill themselves on their first run.

### Forecasts

| File | Contents | Key |
|---|---|---|
| [`data/forecasts_weather.csv`](data/forecasts_weather.csv) | Max/min temperature and rainfall for each city, 1 and 2 days after the latest complete day | target_date + city + horizon_days |
| [`data/forecasts_dengue.csv`](data/forecasts_dengue.csv) | Next week's dengue cases per district; `method` says whether the model or the persistence fallback produced it | year + week + district |

Forecasts are never rewritten once published, so they can be scored against what
actually happened. Accuracy is in [`FORECASTS.md`](FORECASTS.md).

All files are plain CSV with a header row. Load them directly, for example
(for a private copy of the repo, read the files from a local clone instead):

```python
import pandas as pd
url = "https://raw.githubusercontent.com/dhananjaya-hbc/lanka-data-tracker/main/data/weather.csv"
df = pd.read_csv(url, parse_dates=["date"])
```

## How the automation works

```
07:00 Sri Lanka (01:30 UTC), daily
    ├─ weather.py, exchange_rates.py, river_discharge.py, solar.py,
    │  fuel_prices.py, world_bank.py, dengue.py, earthquakes.py
    └─ validate ─► save to data/

01:00, 05:00, 09:00, 13:00, 17:00, 21:00 Sri Lanka, every 4 hours
    ├─ weather_snapshots.py, air_quality.py, marine.py, cbsl_rates.py,
    │  cse_market.py, earthquakes.py
    └─ validate ─► save to data/
```

- **Standard library only:** no `pip install`, so a run takes seconds.
- **Retries:** every HTTP request is retried 3 times with exponential backoff.
- **No duplicates:** every file is deduplicated on its key (see the table above),
  so re-running the workflow is always safe. Sources that revise figures
  (World Bank, CBSL, CSE) update the existing row instead of adding a new one.
- **Backfill:** dengue (all reports listed on the NDCU site) and fuel prices
  (CPC's full history) fill in past data on their first run.
- **Independent sources:** if one source fails, the others are still saved.
  The run is marked failed afterwards so the problem is visible.
- **Validation:** before saving, [`collectors/validate.py`](collectors/validate.py)
  checks every file: header unchanged, unique keys, and for new or changed rows
  plausible ranges (e.g. 5–45 °C), cross-field rules (min ≤ max temperature, TT buy
  ≤ sell) and jump limits (e.g. USD/LKR moving >15% in a day). A file that fails is
  reverted, so bad data is never saved, and the run is marked failed.
  It then writes [`STATUS.md`](STATUS.md), flagging any source that has gone stale.
- **Alerts:** a failed collector, a rejected file, a stale dataset, a failed save or
  a failed forecast run opens one GitHub issue labelled `data-alert` (GitHub emails
  you); it is closed automatically when the source recovers
  ([`collectors/alerts.py`](collectors/alerts.py)).
- **Tests:** [`tests/`](tests/) checks every scraper against saved copies of the real
  source pages, plus storage, validation and alerts (standard-library `unittest`),
  and renders every dashboard tab. They run on each code push
  ([`tests.yml`](.github/workflows/tests.yml)); if a source changes its layout,
  refresh its file in `tests/fixtures/` and the failing test shows what broke.

The workflow can also be started manually from the Actions tab or with
`gh workflow run daily-collect.yml` (optionally `-f group=daily` or `-f group=snapshot`).

## Forecasting

[`.github/workflows/forecast.yml`](.github/workflows/forecast.yml) runs after every
data collection run and does work only when there is new data:

- **Weather:** gradient-boosted trees (scikit-learn) predict each city's max/min
  temperature and rainfall 1 and 2 days ahead from the previous 7 days and the season.
- **Dengue:** predicts next week's cases per district from the last 4 weeks of cases
  and the last 6 weeks of rainfall, as a week-on-week growth rate.
- **Weekly retraining** every Sunday at 09:00 Sri Lanka time. Each model is first
  scored on recent data it never saw against two baselines (*same as today* and
  *usual for the month*), then refit on all data. Results go to
  [`FORECASTS.md`](FORECASTS.md) and [`models/metrics.json`](models/metrics.json).
- Dengue forecasts use the model only while it beats the baseline on held-out weeks;
  otherwise they fall back to "same as this week".
- Model files are kept in the GitHub Actions cache rather than git (they would add
  ~90 MB a year); if the cache is evicted, the workflow retrains them.

This workflow installs pandas and scikit-learn; data collection stays standard-library only.

```bash
pip install -r forecasting/requirements.txt
python forecasting/train.py && python forecasting/predict.py
```

## Dashboard

[`dashboard/app.py`](dashboard/app.py) is a Streamlit app over the CSVs: today's
conditions across the country, weather and rainfall trends, the dengue heatmap and
dengue-vs-rain by district, air quality and waves, river flow, fuel prices since 1990,
exchange rates, the ASPI, World Bank indicators, and the forecasts.

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

It is live at [lanka-data-tracker-qmeq7gejtnaw6nyhu5jnoz.streamlit.app](https://lanka-data-tracker-qmeq7gejtnaw6nyhu5jnoz.streamlit.app). To publish your own copy free on
[Streamlit Community Cloud](https://share.streamlit.io): sign in
with GitHub, choose **Create app**, pick this repository, branch `main` and main file
`dashboard/app.py`. The app updates itself whenever the data does.

## Run locally

```bash
for c in weather exchange_rates river_discharge solar fuel_prices world_bank dengue \
         weather_snapshots air_quality marine cbsl_rates cse_market earthquakes; do
  python3 collectors/$c.py
done
```

Requires Python 3.9+. No dependencies. Run the tests with `python3 -m unittest discover -s tests`.

To rebuild the historical backfill (rate-limited, about 80 minutes):

```bash
python3 collectors/backfill.py fetch --cache /tmp/backfill
git pull --rebase && python3 collectors/backfill.py merge --cache /tmp/backfill
```

## Project structure

```
collectors/
  common.py             shared helpers: HTTP with retries, CSV append/upsert,
                        HTML to text, Open-Meteo snapshots, city list, Sri Lanka date
  weather.py            daily weather
  exchange_rates.py     exchange rates
  river_discharge.py    river discharge
  solar.py              solar radiation and sunshine
  fuel_prices.py        CPC fuel prices
  world_bank.py         World Bank macro indicators
  dengue.py             NDCU weekly dengue reports (includes a small PDF text reader)
  validate.py           data validation + STATUS.md
  backfill.py           one-off historical backfill (run manually)
  alerts.py             opens/closes GitHub issues for broken sources
  summary.py            writes the README's weekly summary
  weather_snapshots.py  4-hourly weather
  air_quality.py        4-hourly air quality
  marine.py             4-hourly sea conditions
  cbsl_rates.py         CBSL policy rate, inflation, USD TT rates
  cse_market.py         CSE indices and turnover
  earthquakes.py        earthquakes
data/                   the datasets (CSV)
forecasting/
  model.py              feature building shared by training and prediction
  train.py              weekly training, evaluation, FORECASTS.md
  predict.py            publishes forecasts
  needs_update.py       cheap check: is there new data to forecast from?
models/metrics.json     latest evaluation results (model files live in the Actions cache)
dashboard/app.py        Streamlit dashboard
STATUS.md               data health, updated every run
FORECASTS.md            forecast accuracy, updated weekly
.github/workflows/
  daily-collect.yml     data collection (daily + every 4 hours)
  forecast.yml          forecasts + weekly retraining
  tests.yml             unit tests + dashboard smoke test on code pushes
tests/                  unit tests and saved source pages (fixtures)
```

## Roadmap

- [x] **Validation:** schema, range, cross-field and jump checks on every
      run, plus a data-health report ([`STATUS.md`](STATUS.md)).
- [x] **Streamlit dashboard:** every dataset plus the forecasts ([`dashboard/`](dashboard/)).
- [x] **Forecasting models:** 1–2 day weather and next-week dengue forecasts, with a
      weekly workflow that retrains the models and publishes metrics ([`FORECASTS.md`](FORECASTS.md)).
- [ ] **Exchange-rate and ASPI forecasts:** once a few months of daily history exist.
- [ ] More sources: reservoir levels (Irrigation Department), forecast-vs-actual
      weather archive, tourist arrivals (SLTDA).

## License

The code is released under the [MIT License](LICENSE). The datasets remain under
their sources' terms, listed below.

## Data licensing

Weather, air quality, marine and flood data © Open-Meteo, licensed under
[CC BY 4.0](https://open-meteo.com/en/license) (air quality: Copernicus CAMS; river
discharge: Copernicus GloFAS). Earthquake data from the U.S. Geological Survey (public
domain). World Bank data under [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses).
Dengue figures from the National Dengue Control Unit, Ministry of Health; fuel
prices from Ceylon Petroleum Corporation; rates from the Central Bank of Sri Lanka;
market data from the Colombo Stock Exchange. These are published by Sri Lankan
public bodies; this repository republishes them for convenience with attribution. Exchange rates from [ExchangeRate-API](https://www.exchangerate-api.com) (attribution
required by their [terms](https://www.exchangerate-api.com/terms)).
