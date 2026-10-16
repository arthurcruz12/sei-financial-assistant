from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, grangercausalitytests

from macro_data import OfficialMacroHub, OfficialSeries
from sei_agents import AgentResult, MarketDataAgent


FREQ_RANK = {"B": 0, "D": 0, "W": 1, "M": 2, "Q": 3, "A": 4, "Y": 4, "unknown": 2}
RESAMPLE_RULE = {"M": "ME", "Q": "QE", "A": "YE"}


def _normalized_frequency(freq: str) -> str:
    value = (freq or "").upper()
    if value.startswith("Q"):
        return "Q"
    if value.startswith("A") or value.startswith("Y"):
        return "A"
    if value.startswith("W"):
        return "W"
    if value.startswith("D") or value.startswith("B"):
        return "D"
    return "M"


def _coarsest_frequency(series: Iterable[OfficialSeries]) -> str:
    frequencies = [_normalized_frequency(s.frequency) for s in series]
    if not frequencies:
        return "M"
    # Macro-market regressions are monthly at minimum. Daily policy-rate change
    # records should not be treated as independent daily macro observations.
    winner = max(["M", *frequencies], key=lambda f: FREQ_RANK.get(f, 2))
    return winner


def _resample_macro(series: pd.Series, target: str) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    if target == "M":
        return clean.resample("ME").mean()
    if target == "Q":
        return clean.resample("QE").mean()
    if target == "A":
        return clean.resample("YE").mean()
    return clean


def _market_returns(close: pd.Series, target: str) -> pd.Series:
    close = pd.to_numeric(close, errors="coerce").dropna().sort_index()
    if target == "M":
        sampled = close.resample("ME").last()
    elif target == "Q":
        sampled = close.resample("QE").last()
    elif target == "A":
        sampled = close.resample("YE").last()
    else:
        sampled = close
    return sampled.pct_change() * 100.0


def _adf_summary(series: pd.Series) -> Dict[str, Optional[float]]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 20 or clean.nunique() < 4:
        return {"statistic": None, "p_value": None, "observations": int(len(clean))}
    try:
        result = adfuller(clean, autolag="AIC")
        return {
            "statistic": round(float(result[0]), 4),
            "p_value": round(float(result[1]), 6),
            "observations": int(result[3]),
        }
    except Exception:
        return {"statistic": None, "p_value": None, "observations": int(len(clean))}


class MacroDataAgent:
    def __init__(self, hub: Optional[OfficialMacroHub] = None) -> None:
        self.hub = hub or OfficialMacroHub()

    def retrieve(self, aliases: List[str], *, start: Optional[str] = None, end: Optional[str] = None) -> AgentResult:
        if not aliases:
            raise ValueError("Nenhuma série macroeconómica foi identificada.")
        payload: Dict[str, Dict] = {}
        sources: List[str] = []
        warnings: List[str] = []
        for alias in aliases:
            try:
                series = self.hub.get(alias, start=start, end=end)
                latest = series.latest()
                payload[alias] = {
                    "name": series.name,
                    "source": series.source,
                    "series_id": series.series_id,
                    "frequency": series.frequency,
                    "unit": series.unit,
                    "observations": int(series.data.dropna().shape[0]),
                    "latest": latest,
                    "source_url": series.source_url,
                }
                sources.append(f"{series.source}: {series.source_url}")
            except Exception as exc:
                warnings.append(f"{alias}: {exc}")
        if not payload:
            raise ValueError("Nenhuma das fontes oficiais solicitadas devolveu dados válidos.")
        return AgentResult(
            agent="official_macro_data",
            summary=f"Dados oficiais carregados para {len(payload)} série(s).",
            data=payload,
            sources=sources,
            warnings=warnings,
        )


class MacroEconometricsAgent:
    """Econometrics over market returns and official macroeconomic series."""

    def __init__(self, market_data: Optional[MarketDataAgent] = None, hub: Optional[OfficialMacroHub] = None) -> None:
        self.market = market_data or MarketDataAgent()
        self.hub = hub or OfficialMacroHub()

    def _load_macros(self, aliases: List[str], start: Optional[str], end: Optional[str]) -> List[OfficialSeries]:
        loaded = []
        for alias in aliases:
            loaded.append(self.hub.get(alias, start=start, end=end))
        return loaded

    def market_vs_macro(
        self,
        symbol: str,
        macro_aliases: List[str],
        *,
        period: str = "10y",
        start: Optional[str] = None,
        end: Optional[str] = None,
        max_macros: int = 4,
    ) -> AgentResult:
        if not symbol:
            raise ValueError("Informe um ticker para cruzar mercado com macroeconomia.")
        if not macro_aliases:
            raise ValueError("Informe pelo menos uma série macroeconómica.")

        macros = self._load_macros(macro_aliases[:max_macros], start, end)
        target_freq = _coarsest_frequency(macros)
        market = self.market.history(symbol, period=period)
        market_return = _market_returns(market["Close"], target_freq).rename(symbol.upper())

        columns = [market_return]
        source_map: Dict[str, str] = {}
        for alias, official in zip(macro_aliases[:max_macros], macros):
            macro = _resample_macro(official.data, target_freq).rename(alias)
            columns.append(macro)
            source_map[alias] = official.source_url

        panel = pd.concat(columns, axis=1, join="inner").dropna()
        if len(panel) < 20:
            raise ValueError(
                f"Apenas {len(panel)} observações comuns após alinhar as frequências. "
                "É insuficiente para uma regressão com alguma estabilidade."
            )

        y_name = symbol.upper()
        x_names = list(panel.columns[1:])
        y = panel[y_name]
        X = sm.add_constant(panel[x_names])
        model = sm.OLS(y, X).fit(cov_type="HC3")

        coefficients: Dict[str, Dict[str, float]] = {}
        for name in model.params.index:
            coefficients[str(name)] = {
                "coef": round(float(model.params[name]), 6),
                "p_value": round(float(model.pvalues[name]), 6),
                "std_error_hc3": round(float(model.bse[name]), 6),
            }

        correlation = panel.corr().round(4).to_dict()
        adf = {name: _adf_summary(panel[name]) for name in panel.columns}

        granger: Dict[str, Dict[str, float]] = {}
        if len(x_names) == 1 and len(panel) >= 48:
            maxlag = min(4, max(1, len(panel) // 20))
            pair = panel[[y_name, x_names[0]]]
            try:
                tests = grangercausalitytests(pair, maxlag=maxlag, verbose=False)
                granger[x_names[0]] = {
                    str(lag): round(float(details[0]["ssr_ftest"][1]), 6)
                    for lag, details in tests.items()
                }
            except Exception:
                granger = {}

        data = {
            "dependent_market_return_percent": y_name,
            "macro_explanatory": x_names,
            "aligned_frequency": target_freq,
            "observations": int(model.nobs),
            "sample_start": str(panel.index.min().date()),
            "sample_end": str(panel.index.max().date()),
            "r_squared": round(float(model.rsquared), 4),
            "adjusted_r_squared": round(float(model.rsquared_adj), 4),
            "coefficients": coefficients,
            "correlation_matrix": correlation,
            "adf": adf,
            "granger_macro_to_market_p_values": granger,
            "source_series": source_map,
            "method_notes": [
                "Mercado é convertido em retorno percentual na frequência macroeconómica comum.",
                "Séries macro de frequência superior são agregadas pela média para a frequência comum.",
                "OLS usa erros-padrão robustos HC3.",
                "Correlação, OLS e Granger não demonstram causalidade estrutural.",
                "A análise usa período de referência das estatísticas; não incorpora automaticamente a data exata de publicação nem vintages/revisões. Portanto não deve ser tratada como backtest sem look-ahead.",
            ],
        }
        sources = [f"Yahoo Finance via yfinance ({symbol.upper()})"] + [f"{m.source}: {m.source_url}" for m in macros]
        warnings = []
        if target_freq == "Q" and len(panel) < 40:
            warnings.append("A regressão trimestral tem amostra curta; interprete coeficientes e p-values com cautela.")
        if float(model.rsquared) > 0.8 and any(adf[name]["p_value"] is not None and adf[name]["p_value"] > 0.05 for name in x_names):
            warnings.append("Há série explicativa possivelmente não estacionária; um R² alto pode ser espúrio. Considere diferenças/cointegração.")

        return AgentResult(
            agent="macro_econometrics",
            summary=f"Regressão de retornos de {y_name} contra {', '.join(x_names)} usando dados oficiais alinhados em frequência {target_freq}.",
            data=data,
            sources=sources,
            warnings=warnings,
        )

    def macro_vs_macro(self, aliases: List[str], *, start: Optional[str] = None, end: Optional[str] = None) -> AgentResult:
        if len(aliases) < 2:
            raise ValueError("A regressão macro-macro requer pelo menos duas séries.")
        macros = self._load_macros(aliases[:5], start, end)
        target_freq = _coarsest_frequency(macros)
        columns = [_resample_macro(s.data, target_freq).rename(alias) for alias, s in zip(aliases[:5], macros)]
        panel = pd.concat(columns, axis=1, join="inner").dropna()
        if len(panel) < 20:
            raise ValueError(f"Apenas {len(panel)} observações comuns; amostra insuficiente.")
        y_name = aliases[0]
        x_names = aliases[1:len(columns)]
        y = panel[y_name]
        X = sm.add_constant(panel[x_names])
        model = sm.OLS(y, X).fit(cov_type="HC3")
        coefficients = {
            str(name): {
                "coef": round(float(model.params[name]), 6),
                "p_value": round(float(model.pvalues[name]), 6),
                "std_error_hc3": round(float(model.bse[name]), 6),
            }
            for name in model.params.index
        }
        data = {
            "dependent": y_name,
            "explanatory": x_names,
            "aligned_frequency": target_freq,
            "observations": int(model.nobs),
            "r_squared": round(float(model.rsquared), 4),
            "adjusted_r_squared": round(float(model.rsquared_adj), 4),
            "coefficients": coefficients,
            "correlation_matrix": panel.corr().round(4).to_dict(),
            "adf": {name: _adf_summary(panel[name]) for name in panel.columns},
            "method_notes": [
                "OLS com erros robustos HC3.",
                "As séries são alinhadas pela frequência mais baixa presente.",
                "Resultados são associativos e não demonstram causalidade.",
            ],
        }
        return AgentResult(
            agent="macro_econometrics",
            summary=f"Regressão macro oficial: {y_name} em função de {', '.join(x_names)}.",
            data=data,
            sources=[f"{m.source}: {m.source_url}" for m in macros],
        )
