import unittest

from sei_agents import FinancialMathAgent
from sei_runtime import RichRouterAgent


class NoLLM:
    def route(self, message):
        return None


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.router = RichRouterAgent(NoLLM())

    def test_probability_request_extracts_symbol_target_and_horizon(self):
        route = self.router.route("Qual a chance de AAPL atingir 300 em 20 dias?")
        self.assertEqual(route.intent, "target_probability")
        self.assertEqual(route.symbol, "AAPL")
        self.assertEqual(route.target_price, 300.0)
        self.assertEqual(route.horizon, 20)

    def test_alias_and_vocabulary(self):
        route = self.router.route("A Nvidia está sobrecomprada ou esticada?")
        self.assertEqual(route.intent, "market_analysis")
        self.assertEqual(route.symbol, "NVDA")

    def test_brazilian_ticker(self):
        route = self.router.route("Analisa o RSI de PETR4")
        self.assertEqual(route.symbol, "PETR4.SA")


class MathTests(unittest.TestCase):
    def test_future_value(self):
        result = FinancialMathAgent().run(
            "future_value",
            {"principal": 1000, "annual_rate": 5, "years": 1, "compounds_per_year": 1},
        )
        self.assertEqual(result.data["future_value"], 1050.0)

    def test_real_return(self):
        result = FinancialMathAgent().run(
            "real_return",
            {"nominal_return": 10, "inflation": 5},
        )
        self.assertAlmostEqual(result.data["real_return_percent"], 4.7619, places=4)


if __name__ == "__main__":
    unittest.main()
