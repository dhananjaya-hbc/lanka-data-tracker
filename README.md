# lanka-data-tracker

[![Data collection](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/daily-collect.yml/badge.svg)](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/daily-collect.yml)

An open, self-updating dataset of Sri Lankan data. A GitHub Actions workflow fetches
the latest values from free public APIs every morning (daily sources) and every 4 hours
(snapshots), appends them to CSV files in [`data/`](data/), and commits the result.
Nobody has to do anything by hand.

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
  so each commit's diff shows the revision.

**cbsl_rates.csv**: `date, ccpi_inflation_pct, overnight_policy_rate_pct, usd_tt_buy, usd_tt_sell`

- As shown on the CBSL website on that weekday (TT rates are quoted at 9:30 a.m.;
  recorded from 13:00 Sri Lanka time). Public holidays repeat the last business day.

**cse_market.csv**: `date, aspi, aspi_change, aspi_change_pct, sp_sl20, sp_sl20_change, sp_sl20_change_pct, turnover_lkr, share_volume, trades`

- Taken from the JSON endpoints behind cse.lk (unofficial). Runs during trading
  hours store intraday values; later runs overwrite them, so each row ends at the close.

All files are plain CSV with a header row. Load them directly, for example:

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
    └─ one commit per changed file ─► git pull --rebase ─► git push

01:00, 05:00, 09:00, 13:00, 17:00, 21:00 Sri Lanka, every 4 hours
    ├─ weather_snapshots.py, air_quality.py, marine.py, cbsl_rates.py,
    │  cse_market.py, earthquakes.py
    └─ one commit per changed file ─► git pull --rebase ─► git push
```

Commit messages: `data: <source> update YYYY-MM-DD` for daily sources and
`data: <source> update YYYY-MM-DD HH:MM` (Sri Lanka time) for snapshots, e.g.
`data: air quality update 2026-10-06 09:00`.

- **Standard library only:** no `pip install`, so a run takes seconds.
- **Retries:** every HTTP request is retried 3 times with exponential backoff.
- **No duplicates:** every file is deduplicated on its key (see the table above),
  so re-running the workflow is always safe. Sources that revise figures
  (World Bank, CBSL, CSE) update the existing row instead of adding a new one.
- **Backfill:** dengue (all reports listed on the NDCU site) and fuel prices
  (CPC's full history) fill in past data on their first run.
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
for c in weather exchange_rates river_discharge solar fuel_prices world_bank dengue \
         weather_snapshots air_quality marine cbsl_rates cse_market earthquakes; do
  python3 collectors/$c.py
done
```

Requires Python 3.9+. No dependencies.

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
  weather_snapshots.py  4-hourly weather
  air_quality.py        4-hourly air quality
  marine.py             4-hourly sea conditions
  cbsl_rates.py         CBSL policy rate, inflation, USD TT rates
  cse_market.py         CSE indices and turnover
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
- [ ] More sources: reservoir levels (Irrigation Department), forecast-vs-actual
      weather archive, tourist arrivals (SLTDA).

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
