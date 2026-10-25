# Forecasts

Models retrained 2026-10-25 14:10 (Sri Lanka time) by the weekly forecast workflow. Forecasts are in [`data/forecasts_weather.csv`](data/forecasts_weather.csv) and [`data/forecasts_dengue.csv`](data/forecasts_dengue.csv).

Each model is scored on recent data it was **not** trained on and compared with two baselines: *persistence* (tomorrow = today) and *climatology* (the usual value for that city and month). **Skill** is the error reduction against the better baseline; negative skill means the model is worse than the baseline.

## Weather (26 cities)

Trained on 64,714 city-days (2020-01-01 to 2026-10-24); tested on 2025-10-25 to 2026-10-24.

| Target | Days ahead | Model MAE | Persistence MAE | Climatology MAE | Skill |
|---|---:|---:|---:|---:|---:|
| Max temperature (°C) | 1 | 0.82 | 0.90 | 1.35 | +9% |
| Max temperature (°C) | 2 | 0.97 | 1.09 | 1.35 | +12% |
| Min temperature (°C) | 1 | 0.54 | 0.60 | 0.80 | +10% |
| Min temperature (°C) | 2 | 0.65 | 0.76 | 0.80 | +14% |
| Rainfall (mm) | 1 | 4.82 | 5.40 | 5.84 | +11% |
| Rainfall (mm) | 2 | 5.40 | 6.80 | 5.84 | +7% |

## Dengue (26 districts, next week's cases)

Trained on 988 district-weeks (38 weeks); tested on 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W39. The model predicts the week-on-week growth rate. Few weeks of history exist so far, so it is experimental: published forecasts use the model only while it beats *persistence* (next week = this week) on held-out weeks. **Currently publishing: model.**

| Target | Model MAE | Persistence MAE | Skill |
|---|---:|---:|---:|
| Cases next week (per district) | 10.8 | 14.3 | +24% |

## Live accuracy (published forecasts, last 30 days)

| Target | Days ahead | Forecasts | MAE |
|---|---:|---:|---:|
| Max temperature (°C) | 1 | 494 | 0.90 |
| Min temperature (°C) | 1 | 494 | 0.41 |
| Rainfall (mm) | 1 | 494 | 7.68 |
| Max temperature (°C) | 2 | 468 | 1.10 |
| Min temperature (°C) | 2 | 468 | 0.46 |
| Rainfall (mm) | 2 | 468 | 8.80 |

MAE = mean absolute error, in the target's units (°C, mm, cases).
