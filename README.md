# lanka-data-tracker

[![Daily data collection](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/daily-collect.yml/badge.svg)](https://github.com/dhananjaya-hbc/lanka-data-tracker/actions/workflows/daily-collect.yml)

An open, self-updating dataset of Sri Lankan data. Every morning a GitHub Actions
workflow fetches the latest values from free public APIs, appends them to CSV files
in [`data/`](data/), and commits the result. Nobody has to do anything by hand.

## Datasets

| File | Contents | Granularity | Source |
|---|---|---|---|
| [`data/weather.csv`](data/weather.csv) | Yesterday's daily max/min temperature (°C), precipitation sum (mm), max wind speed (km/h), mean relative humidity (%) for Wellawaya, Colombo, Kandy, Galle, Jaffna, Nuwara Eliya, Trincomalee | 1 row per date + city | [Open-Meteo](https://open-meteo.com/) |
| [`data/exchange_rates.csv`](data/exchange_rates.csv) | LKR per 1 unit of USD, EUR, GBP, INR, JPY, AUD, CNY, AED | 1 row per date + currency | [ExchangeRate-API open access](https://www.exchangerate-api.com/docs/free) (`open.er-api.com`) |

### Columns

**weather.csv**: `date, city, latitude, longitude, temp_max_c, temp_min_c, precipitation_mm, wind_speed_max_kmh, humidity_mean_pct`

- `date` is the Sri Lanka calendar day the values describe, always a complete
  day (the collector stores *yesterday*).

**exchange_rates.csv**: `date, currency, lkr_per_unit, source_updated_utc`

- `date` is the UTC date the provider last published its rates, so a stale
  response is never recorded under a newer date.
- `lkr_per_unit` is derived from USD-based rates: `rates[LKR] / rates[currency]`.

Both files are plain CSV with a header row. Load them directly, for example:

```python
import pandas as pd
url = "https://raw.githubusercontent.com/dhananjaya-hbc/lanka-data-tracker/main/data/weather.csv"
df = pd.read_csv(url, parse_dates=["date"])
```

## How the automation works

```
01:30 UTC (07:00 Sri Lanka) ─► GitHub Actions: daily-collect.yml
    ├─ collectors/weather.py          ─► data/weather.csv          (continue-on-error)
    ├─ collectors/exchange_rates.py   ─► data/exchange_rates.csv   (continue-on-error)
    └─ git commit "data: daily update YYYY-MM-DD" ─► git pull --rebase ─► git push
```

- **Standard library only:** no `pip install`, so a run takes seconds.
- **Retries:** every HTTP request is retried 3 times with exponential backoff.
- **No duplicates:** rows are deduplicated on `date + city` / `date + currency`,
  so re-running the workflow (or running it twice in a day) is always safe.
- **Independent sources:** if one source fails, the others still save and commit.
  The run is marked failed afterwards so the problem is visible.
- **No empty commits:** if nothing new was collected, the commit is skipped.
- **Safe pushes:** a concurrency group prevents overlapping runs, and the job runs
  `git pull --rebase` before pushing.
- **Commit author:** taken from the repository variables `COMMIT_NAME` and
  `COMMIT_EMAIL`, falling back to `github-actions[bot]`.

The workflow can also be started manually from the Actions tab or with
`gh workflow run daily-collect.yml`.

## Run locally

```bash
python3 collectors/weather.py
python3 collectors/exchange_rates.py
```

Requires Python 3.9+. No dependencies.

## Project structure

```
collectors/
  common.py           shared helpers: HTTP with retries, CSV dedupe/append, Sri Lanka date
  weather.py          Open-Meteo collector
  exchange_rates.py   exchange rate collector
data/                 the datasets (CSV), appended daily
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
- [ ] More sources: air quality, fuel prices, CSE market indices.

## Data licensing

Weather data © Open-Meteo, licensed under [CC BY 4.0](https://open-meteo.com/en/license).
Exchange rates from [ExchangeRate-API](https://www.exchangerate-api.com) (attribution
required by their [terms](https://www.exchangerate-api.com/terms)).
