# Forecasts

Models retrained 2026-11-15 16:54 (Sri Lanka time) by the weekly forecast workflow. Forecasts are in [`data/forecasts_weather.csv`](data/forecasts_weather.csv) and [`data/forecasts_dengue.csv`](data/forecasts_dengue.csv).

Each model is scored on recent data it was **not** trained on and compared with two baselines: *persistence* (tomorrow = today) and *climatology* (the usual value for that city and month). **Skill** is the error reduction against the better baseline; negative skill means the model is worse than the baseline.

## Weather (26 cities)

Trained on 65,260 city-days (2020-01-01 to 2026-11-14); tested on 2025-11-15 to 2026-11-14.

| Target | Days ahead | Model MAE | Persistence MAE | Climatology MAE | Skill |
|---|---:|---:|---:|---:|---:|
| Max temperature (°C) | 1 | 0.84 | 0.93 | 1.35 | +10% |
| Max temperature (°C) | 2 | 0.97 | 1.11 | 1.35 | +13% |
| Min temperature (°C) | 1 | 0.54 | 0.59 | 0.80 | +10% |
| Min temperature (°C) | 2 | 0.64 | 0.75 | 0.80 | +14% |
| Rainfall (mm) | 1 | 5.04 | 5.79 | 5.89 | +13% |
| Rainfall (mm) | 2 | 5.57 | 7.30 | 5.87 | +5% |

## Dengue (26 districts, next week's cases)

Trained on 988 district-weeks (38 weeks); tested on 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W39. The model predicts the week-on-week growth rate. Few weeks of history exist so far, so it is experimental: published forecasts use the model only while it beats *persistence* (next week = this week) on held-out weeks. **Currently publishing: model.**

| Target | Model MAE | Persistence MAE | Skill |
|---|---:|---:|---:|
| Cases next week (per district) | 10.8 | 14.3 | +24% |

## Live accuracy (published forecasts, last 30 days)

| Target | Days ahead | Forecasts | MAE |
|---|---:|---:|---:|
| Max temperature (°C) | 1 | 780 | 1.05 |
| Min temperature (°C) | 1 | 780 | 0.46 |
| Rainfall (mm) | 1 | 780 | 8.77 |
| Max temperature (°C) | 2 | 780 | 1.16 |
| Min temperature (°C) | 2 | 780 | 0.54 |
| Rainfall (mm) | 2 | 780 | 9.65 |

MAE = mean absolute error, in the target's units (°C, mm, cases).
