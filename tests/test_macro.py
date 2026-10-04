import unittest

import numpy as np
import pandas as pd

from macro_analysis import MacroEconometricsAgent
from macro_data import EurostatConnector, INEConnector, OfficialSeries, _infer_frequency, _period_to_timestamp
from sei_macro_runtime import MacroIntentParser


class PeriodParsingTests(unittest.TestCase):
    def test_ine_month_period(self):
        self.assertEqual(str(_period_to_timestamp("202608").date()), "2026-08-31")
        self.assertEqual(str(_period_to_timestamp("S3A202608").date()), "2026-08-31")

    def test_quarter_period(self):
        self.assertEqual(str(_period_to_timestamp("2026-Q2").date()), "2026-06-30")
        self.assertEqual(str(_period_to_timestamp("S4A2026T2").date()), "2026-06-30")

    def test_frequency_inference(self):
        self.assertEqual(_infer_frequency(["S3A202608", "S3A202607"]), "M")
        self.assertEqual(_infer_frequency(["2026-Q2", "2026-Q1"]), "Q")
        self.assertEqual(_infer_frequency(["2025", "2024"]), "A")


class EurostatParsingTests(unittest.TestCase):
    def _payload(self, values):
        return {
            "id": ["geo", "time"],
            "size": [1, 2],
            "dimension": {
                "geo": {"category": {"index": {"PT": 0}}},
                "time": {"category": {"index": {"2026-01": 0, "2026-02": 1}}},
            },
            "value": values,
        }

    def test_sparse_dict_jsonstat_values(self):
        frame = EurostatConnector._flatten_jsonstat(self._payload({"0": 2.1, "1": 2.3}))
        self.assertEqual(frame["geo"].tolist(), ["PT", "PT"])
        self.assertEqual(frame["OBS_VALUE"].tolist(), [2.1, 2.3])

    def test_list_jsonstat_values(self):
        frame = EurostatConnector._flatten_jsonstat(self._payload([2.1, 2.3]))
        self.assertEqual(frame["time"].tolist(), ["2026-01", "2026-02"])
        self.assertEqual(frame["OBS_VALUE"].tolist(), [2.1, 2.3])


class INEParsingTests(unittest.TestCase):
    def test_extract_rows(self):
        payload = [{
            "IndicadorDsg": "Teste",
            "Dados": {
                "S3A202601": [{"valor": "2.0", "geocod": "PT"}],
                "S3A202602": [{"valor": "2.1", "geocod": "PT"}],
            },
        }]
        root, rows = INEConnector._extract_rows(payload)
        self.assertEqual(root["IndicadorDsg"], "Teste")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["period"], "S3A202602")


class MacroIntentTests(unittest.TestCase):
    def setUp(self):
        self.parser = MacroIntentParser()

    def test_market_macro_question(self):
        aliases = self.parser.aliases("Cruza SPY com inflação e Euribor nos últimos 10 anos")
        self.assertIn("pt_inflation_ine", aliases)
        self.assertIn("euribor3m", aliases)
        self.assertTrue(self.parser.wants_cross_analysis("Cruza SPY com inflação e Euribor"))
        self.assertEqual(self.parser.period("nos últimos 10 anos"), "10y")

    def test_explicit_eurostat(self):
        aliases = self.parser.aliases("Use Eurostat para comparar desemprego e PIB")
        self.assertEqual(aliases, ["pt_unemployment_eurostat", "pt_gdp_qoq_eurostat"])

    def test_explicit_oecd(self):
        self.assertEqual(self.parser.aliases("OECD desemprego de Portugal"), ["pt_unemployment_oecd"])

    def test_euribor_tenor(self):
        self.assertEqual(self.parser.aliases("Euribor 12 meses"), ["euribor12m"])
        self.assertEqual(self.parser.aliases("Euribor 6 meses"), ["euribor6m"])


class FakeMarket:
    def history(self, symbol, period="10y"):
        idx = pd.date_range("2016-01-01", periods=120, freq="ME")
        rng = np.random.default_rng(42)
        macro = np.linspace(0, 5, len(idx))
        returns = 0.002 + 0.0004 * macro + rng.normal(0, 0.01, len(idx))
        close = 100 * np.cumprod(1 + returns)
        return pd.DataFrame({"Close": close}, index=idx)


class FakeHub:
    def get(self, alias, start=None, end=None):
        idx = pd.date_range("2016-01-31", periods=120, freq="ME")
        values = np.linspace(0, 5, len(idx))
        return OfficialSeries(
            name=alias,
            source="Fake official",
            series_id=alias,
            frequency="M",
            unit="percent",
            data=pd.Series(values, index=idx),
            source_url="https://example.test/series",
        )


class MacroEconometricsTests(unittest.TestCase):
    def test_market_vs_macro_returns_structured_result(self):
        agent = MacroEconometricsAgent(FakeMarket(), FakeHub())
        result = agent.market_vs_macro("SPY", ["pt_inflation_ine"], period="10y")
        self.assertEqual(result.agent, "macro_econometrics")
        self.assertEqual(result.data["aligned_frequency"], "M")
        self.assertGreaterEqual(result.data["observations"], 100)
        self.assertIn("pt_inflation_ine", result.data["coefficients"])
        self.assertIn("p_value", result.data["coefficients"]["pt_inflation_ine"])


if __name__ == "__main__":
    unittest.main()
