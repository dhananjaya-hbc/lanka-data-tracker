"""Tests for CSV storage (dedupe/upsert), the daily lookback and validation."""

import csv
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "collectors"))

import common  # noqa: E402
import validate  # noqa: E402
import weather  # noqa: E402


class TempDataDir(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._orig = common.DATA_DIR, validate.DATA_DIR
        common.DATA_DIR = validate.DATA_DIR = self.dir

    def tearDown(self):
        common.DATA_DIR, validate.DATA_DIR = self._orig

    def read(self, name):
        with open(os.path.join(self.dir, name), newline="") as f:
            return list(csv.DictReader(f))


class StorageTest(TempDataDir):
    FIELDS = ["date", "city", "value"]

    def test_append_skips_existing_and_repeated_keys(self):
        rows = [{"date": "2026-10-05", "city": "Colombo", "value": 1},
                {"date": "2026-10-05", "city": "Colombo", "value": 2}]
        self.assertEqual(common.append_rows("t.csv", self.FIELDS, rows, ["date", "city"]), 1)
        self.assertEqual(common.append_rows("t.csv", self.FIELDS, rows, ["date", "city"]), 0)
        self.assertEqual([r["value"] for r in self.read("t.csv")], ["1"])

    def test_upsert_updates_changed_rows_only(self):
        key = ["date"]
        fields = ["date", "value"]
        self.assertEqual(common.upsert_rows("u.csv", fields, [{"date": "d1", "value": 1}], key), (1, 0))
        self.assertEqual(common.upsert_rows("u.csv", fields, [{"date": "d1", "value": 1}], key), (0, 0))
        self.assertEqual(common.upsert_rows("u.csv", fields, [{"date": "d1", "value": 2},
                                                              {"date": "d2", "value": 3}], key), (1, 1))
        self.assertEqual([(r["date"], r["value"]) for r in self.read("u.csv")], [("d1", "2"), ("d2", "3")])

    def test_html_to_text_keeps_cells_separable(self):
        self.assertEqual(common.html_to_text("<td>TT Buy</td><td> 326.1 </td><script>x</script>"),
                         " | TT Buy | 326.1 | ")


class RetryTest(unittest.TestCase):
    def attempts(self, error):
        calls = []

        def fail(*a, **k):
            calls.append(1)
            raise error
        with mock.patch("urllib.request.urlopen", fail), mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError):
                common.fetch_bytes("https://example.invalid/x", retries=3)
        return len(calls)

    def test_not_found_is_not_retried(self):
        self.assertEqual(self.attempts(urllib.error.HTTPError("u", 404, "Not Found", {}, None)), 1)

    def test_server_errors_and_timeouts_are_retried(self):
        self.assertEqual(self.attempts(urllib.error.HTTPError("u", 503, "Unavailable", {}, None)), 4)
        self.assertEqual(self.attempts(TimeoutError("slow")), 4)


class WeatherLookbackTest(unittest.TestCase):
    def fake_response(self, today, values):
        days = [(today - timedelta(days=n)).isoformat() for n in range(len(values) - 1, -1, -1)]
        return {"daily": {"time": days, **{var: list(values) for var in weather.VARIABLES}}}

    def test_returns_complete_past_days_but_not_today(self):
        today = date(2026, 10, 6)
        weather.fetch_json = lambda url: self.fake_response(today, [1, 2, 3, 4, 5, 6, 7, 8])
        rows = weather.fetch_city("Colombo", 6.9, 79.8, today)
        self.assertEqual([r["date"] for r in rows][-1], "2026-10-05")
        self.assertEqual(len(rows), 7)

    def test_missing_yesterday_is_an_error(self):
        today = date(2026, 10, 6)
        weather.fetch_json = lambda url: self.fake_response(today, [1, 2, 3, 4, 5, 6, None, 8])
        with self.assertRaisesRegex(RuntimeError, "missing values for 2026-10-05"):
            weather.fetch_city("Colombo", 6.9, 79.8, today)


class ValidationTest(TempDataDir):
    HEADER = ["date", "city", "latitude", "longitude", "temp_max_c", "temp_min_c",
              "precipitation_mm", "wind_speed_max_kmh", "humidity_mean_pct"]
    GOOD = "2026-10-04,Colombo,6.9,79.8,31.0,25.0,1.0,10.0,80"

    def check(self, filename, committed_lines, new_lines, header=None):
        header = header or self.HEADER
        committed = "\n".join([",".join(header), *committed_lines]) + "\n"
        with open(os.path.join(self.dir, filename), "w") as f:
            f.write(committed + "\n".join(new_lines) + ("\n" if new_lines else ""))
        validate.committed = lambda name: validate.read_csv(committed)
        return validate.check_file(filename, validate.RULES[filename])

    def test_clean_rows_pass(self):
        self.assertEqual(self.check("weather.csv", [self.GOOD],
                                    ["2026-10-05,Colombo,6.9,79.8,32.0,24.0,0.0,9.0,81"]), [])

    def test_out_of_range_and_cross_field(self):
        errors = self.check("weather.csv", [self.GOOD],
                            ["2026-10-05,Colombo,6.9,79.8,55.0,24.0,0.0,9.0,81",
                             "2026-10-05,Kandy,7.2,80.6,20.0,25.0,0.0,9.0,81"])
        self.assertTrue(any("temp_max_c=55.0 outside" in e for e in errors))
        self.assertTrue(any("fails temp_min_c <= temp_max_c" in e for e in errors))

    def test_history_is_not_rechecked(self):
        # an old out-of-range row already committed does not block new data
        old_bad = "2026-10-03,Colombo,6.9,79.8,55.0,24.0,0.0,9.0,81"
        self.assertEqual(self.check("weather.csv", [old_bad, self.GOOD], []), [])

    def test_duplicate_key(self):
        errors = self.check("weather.csv", [self.GOOD], [self.GOOD])
        self.assertTrue(any("duplicate key" in e for e in errors))

    def test_jump_limit(self):
        header = ["date", "currency", "lkr_per_unit", "source_updated_utc"]
        errors = self.check("exchange_rates.csv", ["2026-10-04,USD,330.0,x"],
                            ["2026-10-05,USD,500.0,x", "2026-10-05,EUR,372.0,x"], header)
        self.assertEqual(len(errors), 1)
        self.assertIn("jumped", errors[0])

    def test_blank_key_allowed_only_where_declared(self):
        header = ["date", "effective_time", "product_code", "product", "price_lkr_per_litre"]
        self.assertEqual(self.check("fuel_prices.csv", [], ["2026-10-01,,LP 92,Petrol,414"], header), [])
        errors = self.check("fuel_prices.csv", [], [",,LP 92,Petrol,414"], header)
        self.assertTrue(any("blank key" in e for e in errors))

    def test_header_change(self):
        committed = io.StringIO()
        csv.writer(committed).writerow(self.HEADER)
        with open(os.path.join(self.dir, "weather.csv"), "w") as f:
            f.write(",".join(self.HEADER + ["extra"]) + "\n")
        validate.committed = lambda name: (self.HEADER, [])
        errors = validate.check_file("weather.csv", validate.RULES["weather.csv"])
        self.assertTrue(any("header changed" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
