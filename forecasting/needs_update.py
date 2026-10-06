"""Decide whether the forecast workflow has work to do (standard library only,
so the check runs before installing pandas/scikit-learn).

Prints `predict=true|false` and `train=true|false` lines for $GITHUB_OUTPUT.
Predict when weather.csv or dengue.csv has data newer than the last published
forecast; train when the model files are missing (they live in the Actions
cache, not in git, and are rebuilt if the cache was evicted).
"""

import csv
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def column_max(name, col):
    path = os.path.join(ROOT, "data", name)
    if not os.path.exists(path):
        return ""
    with open(path, newline="", encoding="utf-8") as f:
        return max((r[col] for r in csv.DictReader(f)), default="")


def main():
    weather = column_max("weather.csv", "date")
    dengue = column_max("dengue.csv", "week_end")
    weather_done = column_max("forecasts_weather.csv", "based_on_date")
    dengue_done = column_max("forecasts_dengue.csv", "week_start")  # = latest report's week + 1
    models = bool(glob.glob(os.path.join(ROOT, "models", "*.joblib")))
    predict = weather > weather_done or (dengue and dengue >= dengue_done)
    print(f"predict={'true' if predict or not models else 'false'}")
    print(f"train={'false' if models else 'true'}")


if __name__ == "__main__":
    main()
