"""Tests for the README weekly summary."""

import os
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "collectors"))

import summary  # noqa: E402

WEATHER = """date,city,latitude,longitude,temp_max_c,temp_min_c,precipitation_mm,wind_speed_max_kmh,humidity_mean_pct
2026-10-04,Colombo,6.9,79.8,31.0,25.0,10.0,10,80
2026-10-05,Colombo,6.9,79.8,32.0,24.0,5.0,10,80
2026-10-05,Nuwara Eliya,6.9,80.7,20.0,12.5,30.0,8,94
"""


class SummaryTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "data"))
        with open(os.path.join(self.root, "data", "weather.csv"), "w") as f:
            f.write(WEATHER)
        self.readme = os.path.join(self.root, "README.md")
        with open(self.readme, "w") as f:
            f.write(f"# Title\n\n{summary.START}\nold\n{summary.END}\n\n## Datasets\n")
        patches = [mock.patch.object(summary, "DATA_DIR", os.path.join(self.root, "data")),
                   mock.patch.object(summary, "REPO_ROOT", self.root)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_main(self, today, *args):
        with mock.patch.object(summary, "sl_today", return_value=today), \
                mock.patch.object(sys, "argv", ["summary.py", *args]):
            self.assertEqual(summary.main(), 0)
        with open(self.readme) as f:
            return f.read()

    def test_section_replaced_and_rest_kept(self):
        text = self.run_main(date(2026, 10, 6))
        self.assertIn("| 🌡️ Hottest | **Colombo**, 32.0 °C on Mon 5 Oct |", text)
        self.assertIn("| 🌙 Coolest night | **Nuwara Eliya**, 12.5 °C", text)
        self.assertIn("| 🌧️ Wettest | **Nuwara Eliya**, 30 mm", text)
        self.assertNotIn("\nold\n", text)
        self.assertTrue(text.startswith("# Title") and text.endswith("## Datasets\n"))

    def test_weekly_waits_for_sunday_or_a_week(self):
        self.run_main(date(2026, 10, 6))                      # Tuesday: generated
        first = self.run_main(date(2026, 10, 8), "--weekly")  # Thursday: too soon
        self.assertIn("Generated 2026-10-06", first)
        sunday = self.run_main(date(2026, 10, 11), "--weekly")
        self.assertIn("Generated 2026-10-11", sunday)


if __name__ == "__main__":
    unittest.main()
