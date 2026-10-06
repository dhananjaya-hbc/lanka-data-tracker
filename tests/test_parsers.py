"""Scraper tests against saved copies of the real source pages (tests/fixtures).

If a source changes its layout, refresh the fixture and these tests show
exactly what broke. Run: python3 -m unittest discover -s tests
"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "collectors"))

import cbsl_rates  # noqa: E402
import common  # noqa: E402
import cse_market  # noqa: E402
import dengue  # noqa: E402
import fuel_prices  # noqa: E402


def fixture(name, mode="r"):
    kwargs = {"encoding": "utf-8"} if mode == "r" else {}
    with open(os.path.join(HERE, "fixtures", name), mode, **kwargs) as f:
        return f.read()


class FuelPricesTest(unittest.TestCase):
    def setUp(self):
        self.rows = fuel_prices.parse(fixture("cpc_historical_prices.html"))

    def price(self, day, code, when=""):
        return [r["price_lkr_per_litre"] for r in self.rows
                if (r["date"], r["product_code"], r["effective_time"]) == (day, code, when)]

    def test_full_history_parsed(self):
        self.assertGreater(len(self.rows), 1500)
        self.assertEqual(min(r["date"] for r in self.rows), "1990-03-01")
        self.assertEqual({r["product_code"] for r in self.rows}, set(fuel_prices.PRODUCTS))

    def test_known_prices(self):
        self.assertEqual(self.price("2026-10-01", "LP 92"), ["414"])
        self.assertEqual(self.price("1990-03-01", "LP 95"), ["22"])

    def test_same_day_revision_kept_separately(self):
        self.assertEqual(self.price("2022-10-17", "FUR. 800"), ["320"])
        self.assertEqual(self.price("2022-10-17", "FUR. 800", "21:00"), ["419"])

    def test_bitumen_table_ignored(self):
        self.assertFalse(any("80/100" in r["product"] for r in self.rows))

    def test_unknown_column_is_an_error(self):
        page = fixture("cpc_historical_prices.html").replace(">LP 92<", ">LP 93<", 1)
        with self.assertRaisesRegex(RuntimeError, "unexpected columns"):
            fuel_prices.parse(page)


class CbslRatesTest(unittest.TestCase):
    def test_rate_window(self):
        values = cbsl_rates.parse(fixture("cbsl_ratewindow.html"))
        self.assertEqual(set(values), set(cbsl_rates.PATTERNS))
        self.assertEqual(values["ccpi_inflation_pct"], "8.00")
        self.assertEqual(values["overnight_policy_rate_pct"], "8.75")
        self.assertLess(float(values["usd_tt_buy"]), float(values["usd_tt_sell"]))

    def test_layout_change_is_an_error(self):
        page = fixture("cbsl_ratewindow.html").replace("TT Sell", "Selling")
        with self.assertRaisesRegex(RuntimeError, "usd_tt_sell not found"):
            cbsl_rates.parse(page)


class DengueTest(unittest.TestCase):
    def table(self, name):
        return dengue.parse_table(dengue.pdf_cells(fixture(name, "rb")))

    def test_week_37(self):
        table = dengue.checked(self.table("dengue_2026_w37.pdf"), 1)
        self.assertEqual(len(table), 26)
        self.assertEqual(table["Colombo"], (222, 207, 23161))  # prev week, week, cumulative
        self.assertEqual(sum(v[1] for v in table.values()), 1156)

    def test_previous_week_column_fills_week_36(self):
        table = dengue.checked(self.table("dengue_2026_w37.pdf"), 0)
        self.assertEqual(sum(v[0] for v in table.values()), 1152)

    def test_ni_typo_reads_as_zero(self):
        table = dengue.checked(self.table("dengue_2026_w27_ni_typo.pdf"), 1)
        self.assertIn("Vavuniya", table)
        self.assertEqual(sum(v[1] for v in table.values()), 7916)

    def test_image_table_is_reported_not_guessed(self):
        with self.assertRaisesRegex(RuntimeError, "Table 1 incomplete"):
            self.table("dengue_2026_w36_image_table.pdf")

    def test_report_links(self):
        links = {(int(y), int(w)) for y, w in
                 (m.groups() for m in dengue.PDF_LINK.finditer(fixture("dengue_weekly_report.html")))}
        self.assertIn((2026, 37), links)
        self.assertIn((2026, 27), links)


class CseMarketTest(unittest.TestCase):
    ASPI = {"value": 20644.26, "change": -168.38, "percentage": -0.809, "timestamp": 1791192420472}
    SNP = {"value": 5847.02, "change": -36.48, "percentage": -0.62, "timestamp": 1791190817215}
    SUMMARY = {"tradeVolume": 3.16e9, "shareVolume": 67643220, "trades": 15781,
               "tradeDate": 1791192420472}

    def run_with(self, aspi, snp, summary):
        bodies = {"aspiData": aspi, "snpData": snp, "marketSummery": summary}
        original, common.DATA_DIR = common.DATA_DIR, tempfile.mkdtemp()
        cse_market.fetch_bytes = lambda url, data=None: (
            b"" if bodies[url.rsplit("/", 1)[1]] is None
            else json.dumps(bodies[url.rsplit("/", 1)[1]]).encode())
        try:
            code = cse_market.main()
            path = os.path.join(common.DATA_DIR, "cse_market.csv")
            if not os.path.exists(path):
                return code, None
            with open(path) as f:
                return code, f.read()
        finally:
            common.DATA_DIR = original

    def test_trading_day(self):
        code, csv_text = self.run_with(self.ASPI, self.SNP, self.SUMMARY)
        self.assertEqual(code, 0)
        self.assertIn("2026-10-05,20644.26", csv_text)

    def test_before_market_open_is_skipped(self):
        self.assertEqual(self.run_with(self.ASPI, None, None), (0, None))

    def test_no_trades_is_skipped(self):
        self.assertEqual(self.run_with(self.ASPI, self.SNP, {**self.SUMMARY, "trades": 0}), (0, None))


if __name__ == "__main__":
    unittest.main()
