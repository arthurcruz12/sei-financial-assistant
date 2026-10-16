import unittest
from unittest.mock import Mock
import pandas as pd

from bcb_data import BCBConnector
from macro_data import OfficialMacroHub


class BCBConnectorTests(unittest.TestCase):
    def test_parse_real_sgs_schema(self):
        response = Mock()
        response.json.return_value = [
            {"data": "01/08/2026", "valor": "0,50"},
            {"data": "01/09/2026", "valor": "0.45"},
        ]
        response.url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"
        session = Mock()
        session.get.return_value = response
        result = BCBConnector(session=session).preset(
            "br_ipca", start="2026-08-01", end="2026-09-30"
        )
        self.assertEqual(result.source, "Banco Central do Brasil (SGS)")
        self.assertEqual(result.frequency, "M")
        self.assertEqual(len(result.data), 2)
        self.assertAlmostEqual(float(result.data.iloc[0]), 0.50)
        self.assertAlmostEqual(float(result.data.iloc[1]), 0.45)
        self.assertEqual(result.data.index[0], pd.Timestamp("2026-08-01"))
        session.get.assert_called_once()
        self.assertEqual(session.get.call_args.kwargs["timeout"], 30)

    def test_empty_response_raises(self):
        response = Mock()
        response.json.return_value = []
        session = Mock()
        session.get.return_value = response
        with self.assertRaisesRegex(ValueError, "sem observações"):
            BCBConnector(session=session).preset(
                "br_ipca", start="2026-08-01", end="2026-09-30"
            )

    def test_reversed_dates_raises_without_request(self):
        session = Mock()
        with self.assertRaises(ValueError):
            BCBConnector(session=session).preset(
                "br_ipca", start="2026-09-30", end="2026-08-01"
            )
        session.get.assert_not_called()

    def test_macro_hub_exposes_brazilian_presets(self):
        hub = OfficialMacroHub()
        self.assertIn("br_ipca", hub.aliases)
        self.assertIn("br_selic_target", hub.aliases)
        self.assertIn("br_usd_brl", hub.aliases)


if __name__ == "__main__":
    unittest.main()
