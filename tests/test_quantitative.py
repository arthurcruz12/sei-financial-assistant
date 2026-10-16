import unittest
import numpy as np
import pandas as pd
from quantitative import log_returns, descriptive_statistics, ols_diagnostics

class QuantitativeTests(unittest.TestCase):
    def test_log_returns(self):
        x = pd.Series([100., 110., 121.], index=pd.date_range("2020-01-01", periods=3))
        r = log_returns(x)
        self.assertEqual(len(r), 2)
        self.assertAlmostEqual(float(r.iloc[0]), 100*np.log(1.1), places=9)

    def test_zero_price_rejected(self):
        with self.assertRaises(ValueError):
            log_returns(pd.Series([100, 0, 110]))

    def test_descriptive_statistics(self):
        d = descriptive_statistics(pd.Series([1.,2.,3.]))
        self.assertEqual(d["observations"], 3)
        self.assertAlmostEqual(d["variance_sample"], 1.0)

    def test_regression_known_signal(self):
        rng = np.random.default_rng(19)
        x = rng.normal(size=120)
        y = 2.0 + 3.0*x + rng.normal(scale=.1,size=len(x))
        panel = pd.DataFrame({"y":y,"x":x}, index=pd.date_range("2016-01-01",periods=len(x),freq="ME"))
        result = ols_diagnostics(panel, "y", ["x"])
        self.assertEqual(result["nobs"],120)
        self.assertAlmostEqual(result["coefficients"]["x"]["estimate"],3,delta=.06)
        self.assertLess(result["coefficients"]["x"]["p_value"],.05)
        self.assertIn("breusch_pagan_p_value",result)

    def test_rank_deficiency(self):
        x = np.arange(50,dtype=float)
        frame = pd.DataFrame({"y":x,"x":x,"same":x})
        with self.assertRaisesRegex(ValueError,"multicollinearity"):
            ols_diagnostics(frame,"y",["x","same"])

if __name__ == "__main__":
    unittest.main()
