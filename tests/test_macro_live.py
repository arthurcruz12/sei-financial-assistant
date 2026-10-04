import os
import unittest

import requests

from macro_data import OfficialMacroHub
from sei_macro_runtime import SEIOfficialMacroHub


LIVE = os.getenv("SEI_LIVE_API_TESTS") == "1"


@unittest.skipUnless(LIVE, "set SEI_LIVE_API_TESTS=1 to test public official APIs")
class OfficialAPISmokeTests(unittest.TestCase):
    def test_ecb_euribor(self):
        series = OfficialMacroHub().ecb.preset("euribor3m", start="2025-01", end="2025-03")
        self.assertGreater(len(series.data), 0)
        self.assertEqual(series.source, "ECB")

    def test_eurostat_inflation(self):
        series = SEIOfficialMacroHub().get("pt_inflation_eurostat", start="2025-01", end="2025-03")
        self.assertGreater(len(series.data), 0)
        self.assertEqual(series.source, "Eurostat")

    def test_ine_inflation(self):
        try:
            series = OfficialMacroHub().ine.preset("pt_inflation_ine")
        except (requests.Timeout, requests.ConnectionError) as exc:
            self.skipTest(f"INE endpoint unavailable from CI runner: {exc}")
        self.assertGreater(len(series.data), 0)
        self.assertEqual(series.source, "INE Portugal")

    def test_oecd_portugal_unemployment(self):
        series = SEIOfficialMacroHub().get("pt_unemployment_oecd", start="2024-Q1", end="2024-Q2")
        self.assertGreater(len(series.data), 0)
        self.assertEqual(series.source, "OECD")

    @unittest.skipUnless(bool(os.getenv("FRED_API_KEY")), "FRED_API_KEY is not configured")
    def test_fred_unemployment(self):
        series = OfficialMacroHub().fred.preset("us_unemployment", start="2025-01-01", end="2025-03-31")
        self.assertGreater(len(series.data), 0)
        self.assertEqual(series.source, "FRED")


if __name__ == "__main__":
    unittest.main()
