# Forecasts

Models retrained 2026-10-06 16:02 (Sri Lanka time) by the weekly forecast workflow. Forecasts are in [`data/forecasts_weather.csv`](data/forecasts_weather.csv) and [`data/forecasts_dengue.csv`](data/forecasts_dengue.csv).

Each model is scored on recent data it was **not** trained on and compared with two baselines: *persistence* (tomorrow = today) and *climatology* (the usual value for that city and month). **Skill** is the error reduction against the better baseline; negative skill means the model is worse than the baseline.

## Weather (26 cities)

Trained on 64,220 city-days (2020-01-01 to 2026-10-05); tested on 2025-10-06 to 2026-10-05.

| Target | Days ahead | Model MAE | Persistence MAE | Climatology MAE | Skill |
|---|---:|---:|---:|---:|---:|
| Max temperature (°C) | 1 | 0.82 | 0.91 | 1.35 | +10% |
| Max temperature (°C) | 2 | 0.96 | 1.09 | 1.35 | +12% |
| Min temperature (°C) | 1 | 0.54 | 0.60 | 0.79 | +10% |
| Min temperature (°C) | 2 | 0.65 | 0.76 | 0.79 | +14% |
| Rainfall (mm) | 1 | 4.85 | 5.40 | 5.89 | +10% |
| Rainfall (mm) | 2 | 5.42 | 6.75 | 5.90 | +8% |

## Dengue (26 districts, next week's cases)

Trained on 936 district-weeks (36 weeks); tested on 2026-W31, 2026-W32, 2026-W33, 2026-W34, 2026-W35, 2026-W36. The model predicts the week-on-week growth rate. Few weeks of history exist so far, so it is experimental: published forecasts use the model only while it beats *persistence* (next week = this week) on held-out weeks. **Currently publishing: model.**

| Target | Model MAE | Persistence MAE | Skill |
|---|---:|---:|---:|
| Cases next week (per district) | 13.7 | 23.8 | +42% |

MAE = mean absolute error, in the target's units (°C, mm, cases).
