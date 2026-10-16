"""Deterministic and auditable SEI statistical calculations."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan, acorr_breusch_godfrey
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import adfuller


def validate_series(values: pd.Series, *, min_count: int = 2, positive: bool = False) -> pd.Series:
    if not isinstance(values, pd.Series):
        raise TypeError("Expected pandas Series.")
    s = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    if s.index.has_duplicates:
        raise ValueError("Duplicate observation dates are not allowed.")
    if len(s) < min_count:
        raise ValueError(f"Insufficient observations: {len(s)}, required {min_count}.")
    if positive and (s <= 0).any():
        raise ValueError("Prices must be strictly positive for log returns.")
    return s


def log_returns(prices: pd.Series) -> pd.Series:
    s = validate_series(prices, positive=True)
    result = np.log(s / s.shift(1)).dropna() * 100
    result.name = "log_return_percent"
    return result


def descriptive_statistics(values: pd.Series) -> dict:
    s = validate_series(values)
    return {
        "observations": int(len(s)), "mean": float(s.mean()),
        "median": float(s.median()), "std_sample": float(s.std(ddof=1)),
        "variance_sample": float(s.var(ddof=1)), "minimum": float(s.min()),
        "maximum": float(s.max()), "start": str(s.index.min()),
        "end": str(s.index.max()),
    }


def ols_diagnostics(panel: pd.DataFrame, dependent: str, explanatory: list[str]) -> dict:
    if dependent in explanatory or not explanatory or len(set(explanatory)) != len(explanatory):
        raise ValueError("Choose distinct dependent and explanatory variables.")
    if any(c not in panel for c in [dependent, *explanatory]):
        raise ValueError("Variables missing from data.")
    data = panel[[dependent, *explanatory]].apply(pd.to_numeric, errors="coerce")
    data = data.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    k = len(explanatory)
    if len(data) < max(30, 10 * (k + 1)):
        raise ValueError("Insufficient common observations for regression diagnostics.")
    X = sm.add_constant(data[explanatory], has_constant="add")
    if np.linalg.matrix_rank(X.to_numpy()) < X.shape[1]:
        raise ValueError("Perfect multicollinearity; regression not identified.")
    fitted = sm.OLS(data[dependent], X).fit(cov_type="HC3")
    classical = sm.OLS(data[dependent], X).fit()
    bp = het_breuschpagan(classical.resid, X)
    bg = acorr_breusch_godfrey(classical, nlags=min(4, len(data)//10))
    stationarity = {}
    for col in data:
        s = data[col]
        try:
            stationarity[col] = float(adfuller(s, autolag="AIC")[1]) if s.nunique() > 3 else None
        except (ValueError, np.linalg.LinAlgError):
            stationarity[col] = None
    return {
        "nobs": int(fitted.nobs), "start": str(data.index.min()),
        "end": str(data.index.max()), "dependent": dependent,
        "explanatory": explanatory, "r_squared": float(fitted.rsquared),
        "adjusted_r_squared": float(fitted.rsquared_adj),
        "coefficients": {
            key: {"estimate": float(fitted.params[key]), "std_error_hc3": float(fitted.bse[key]),
                  "t_stat": float(fitted.tvalues[key]), "p_value": float(fitted.pvalues[key]),
                  "ci95_low": float(fitted.conf_int().loc[key, 0]),
                  "ci95_high": float(fitted.conf_int().loc[key, 1])}
            for key in fitted.params.index
        },
        "correlation": data.corr().to_dict(),
        "breusch_pagan_p_value": float(bp[1]),
        "breusch_godfrey_p_value": float(bg[1]),
        "vif": {name: float(variance_inflation_factor(X.to_numpy(), i))
                for i, name in enumerate(X.columns) if name != "const"},
        "adf_p_values": stationarity,
        "method": "OLS; heteroscedasticity-robust HC3 standard errors; 95% confidence intervals.",
        "caution": "Associations, not causal effects. Publication lags, release vintages and revisions are not handled.",
    }
