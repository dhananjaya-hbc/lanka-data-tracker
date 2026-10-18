# Forecasts

Models retrained 2026-10-18 13:47 (Sri Lanka time) by the weekly forecast workflow. Forecasts are in [`data/forecasts_weather.csv`](data/forecasts_weather.csv) and [`data/forecasts_dengue.csv`](data/forecasts_dengue.csv).

Each model is scored on recent data it was **not** trained on and compared with two baselines: *persistence* (tomorrow = today) and *climatology* (the usual value for that city and month). **Skill** is the error reduction against the better baseline; negative skill means the model is worse than the baseline.

## Weather (26 cities)

Trained on 64,532 city-days (2020-01-01 to 2026-10-17); tested on 2025-10-18 to 2026-10-17.

| Target | Days ahead | Model MAE | Persistence MAE | Climatology MAE | Skill |
|---|---:|---:|---:|---:|---:|
| Max temperature (°C) | 1 | 0.82 | 0.91 | 1.36 | +9% |
| Max temperature (°C) | 2 | 0.96 | 1.10 | 1.36 | +12% |
| Min temperature (°C) | 1 | 0.54 | 0.60 | 0.79 | +10% |
| Min temperature (°C) | 2 | 0.65 | 0.76 | 0.79 | +15% |
| Rainfall (mm) | 1 | 4.82 | 5.43 | 5.87 | +11% |
| Rainfall (mm) | 2 | 5.43 | 6.83 | 5.85 | +7% |

## Dengue (26 districts, next week's cases)

Trained on 988 district-weeks (38 weeks); tested on 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W39. The model predicts the week-on-week growth rate. Few weeks of history exist so far, so it is experimental: published forecasts use the model only while it beats *persistence* (next week = this week) on held-out weeks. **Currently publishing: model.**

| Target | Model MAE | Persistence MAE | Skill |
|---|---:|---:|---:|
| Cases next week (per district) | 10.8 | 14.3 | +24% |

## Live accuracy (published forecasts, last 30 days)

| Target | Days ahead | Forecasts | MAE |
|---|---:|---:|---:|
| Max temperature (°C) | 1 | 312 | 0.93 |
| Min temperature (°C) | 1 | 312 | 0.42 |
| Rainfall (mm) | 1 | 312 | 6.83 |
| Max temperature (°C) | 2 | 286 | 1.09 |
| Min temperature (°C) | 2 | 286 | 0.46 |
| Rainfall (mm) | 2 | 286 | 7.45 |

MAE = mean absolute error, in the target's units (°C, mm, cases).
