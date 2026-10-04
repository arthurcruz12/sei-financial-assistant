from __future__ import annotations

import re
from typing import List, Optional

import numpy as np
import pandas as pd

from sei_agents import (
    AgentResult,
    EconometricsAgent,
    FinancialMathAgent,
    LLMClient,
    MarketDataAgent,
    MIN_BACKTEST_SAMPLE,
    Route,
    RouterAgent,
    SEIOrchestrator,
    StatisticsAgent,
    TechnicalAnalysisAgent,
    ValidatorAgent,
)


VOCABULARY = {
    "technical": [
        "rsi", "macd", "ema", "sma", "vwap", "atr", "adx", "bollinger", "obv",
        "suporte", "support", "resistência", "resistencia", "resistance",
        "rompimento", "romper", "breakout", "breakdown", "pullback", "reteste", "retest",
        "tendência", "tendencia", "trend", "momentum", "divergência", "divergencia",
        "sobrecomprado", "overbought", "sobrevendido", "oversold", "lateral", "consolidação",
        "consolidacao", "canal", "gap", "pivot", "swing", "candlestick", "doji", "hammer",
        "engulfing", "volume", "força compradora", "forca compradora", "pressão compradora",
        "pressao compradora", "força vendedora", "forca vendedora", "pressão vendedora",
        "esticada", "esticado", "gráfico", "grafico", "análise técnica", "analise tecnica",
    ],
    "probability": [
        "chance", "probabilidade", "possibilidade", "odds", "atingir", "chegar", "bater",
        "alvo", "target", "qual a chance", "probabilidade de alta", "probabilidade de queda",
    ],
    "statistics": [
        "estatística", "estatistica", "média", "media", "mediana", "variância", "variancia",
        "desvio padrão", "desvio padrao", "volatilidade", "percentil", "quantil", "distribuição",
        "distribuicao", "skewness", "curtose", "kurtosis", "correlação", "correlacao",
        "covariância", "covariancia", "intervalo de confiança", "p-value", "p value", "bootstrap",
        "monte carlo", "drawdown", "sharpe", "sortino", "win rate", "profit factor",
    ],
    "econometrics": [
        "econometria", "econométrico", "econometrico", "regressão", "regressao", "ols", "logit",
        "probit", "r²", "r2", "heterocedasticidade", "autocorrelação", "autocorrelacao",
        "multicolinearidade", "vif", "endogeneidade", "estacionariedade", "adf", "cointegração",
        "cointegracao", "granger", "arima", "sarima", "var", "vecm", "garch",
    ],
    "research": [
        "pesquise", "procure", "notícia", "noticia", "hoje", "atual", "mais recente", "último",
        "ultimo", "bce", "ecb", "fed", "banco central", "inflação", "inflacao", "pib", "gdp",
        "desemprego", "taxa de juros", "euribor", "yield", "curva de juros", "défice", "defice",
    ],
}

ASSET_ALIASES = {
    "apple": "AAPL",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "meta": "META",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amd": "AMD",
    "s&p 500": "SPY",
    "sp500": "SPY",
    "s&p500": "SPY",
    "nasdaq 100": "QQQ",
    "nasdaq100": "QQQ",
    "bitcoin": "BTC-USD",
    "btc": "BTC-USD",
    "ethereum": "ETH-USD",
    "eth": "ETH-USD",
}


class RichRouterAgent(RouterAgent):
    """LLM-first router with a deterministic Portuguese/English fallback vocabulary."""

    def _extract_symbols(self, message: str) -> List[str]:
        symbols: List[str] = []

        for token in re.findall(r"(?<![A-Za-z0-9])\$([A-Za-z][A-Za-z0-9.-]{0,11})", message):
            symbols.append(token.upper())

        for token in re.findall(r"\b[A-Z]{1,6}(?:-[A-Z]{2,4}|\.[A-Z]{1,4})?\b", message):
            if token not in {"SEI", "RSI", "MACD", "EMA", "SMA", "ATR", "ADX", "VWAP", "OLS", "VAR", "VECM", "ARIMA", "SARIMA", "GARCH", "BCE", "FED"}:
                symbols.append(token)

        for token in re.findall(r"\b([A-Za-z]{4}\d{1,2})(?:\.SA)?\b", message):
            symbols.append(token.upper() + ".SA")

        lower = message.lower()
        for alias, symbol in ASSET_ALIASES.items():
            if alias in lower:
                symbols.append(symbol)

        deduped = []
        for symbol in symbols:
            if symbol not in deduped:
                deduped.append(symbol)
        return deduped

    @staticmethod
    def _contains_any(text: str, words: List[str]) -> bool:
        return any(word in text for word in words)

    def route(self, message: str) -> Route:
        llm_route = self.llm.route(message)
        if llm_route:
            if llm_route.symbol:
                llm_route.symbol = llm_route.symbol.upper()
            return llm_route

        lower = message.lower()
        symbols = self._extract_symbols(message)
        symbol = symbols[0] if symbols else None
        horizon_match = re.search(r"(\d+)\s*(?:dias?|preg[oõ]es?|days?|sessions?)", lower)
        horizon = int(horizon_match.group(1)) if horizon_match else 5
        target_match = re.search(
            r"(?:alvo|target|chegar|bater|atingir)\s*(?:a|em|nos?)?\s*[$€£]?\s*(\d+(?:[.,]\d+)?)",
            lower,
        )
        target = float(target_match.group(1).replace(",", ".")) if target_match else None

        if self._contains_any(lower, VOCABULARY["econometrics"]):
            return Route(intent="econometrics", symbols=symbols, horizon=horizon)
        if self._contains_any(lower, VOCABULARY["statistics"]):
            return Route(intent="statistics", symbol=symbol, horizon=horizon)
        if self._contains_any(lower, VOCABULARY["probability"]):
            return Route(intent="target_probability", symbol=symbol, horizon=horizon, target_price=target)
        if self._contains_any(lower, VOCABULARY["technical"]):
            return Route(intent="market_analysis", symbol=symbol, horizon=horizon)
        if self._contains_any(lower, VOCABULARY["research"]):
            return Route(intent="research", query=message)
        return Route(intent="general", symbol=symbol, symbols=symbols, query=message)


class QuantTechnicalAnalysisAgent(TechnicalAnalysisAgent):
    """Technical agent with relative-target backtesting and regime evidence checks."""

    def _matched_regimes(self, df: pd.DataFrame, horizon: int):
        latest = df.iloc[-1]
        regime = {
            "above_ema200": bool(latest["Close"] > latest["EMA200"]),
            "ema20_above_ema50": bool(latest["EMA20"] > latest["EMA50"]),
            "rsi_bucket": self._rsi_bucket(float(latest["RSI14"])),
            "macd_positive": bool(latest["MACD"] > latest["MACD_SIGNAL"]),
            "high_relative_volume": bool(latest["REL_VOLUME"] >= 1.2),
            "breakout": bool(latest["BREAKOUT"]),
            "breakdown": bool(latest["BREAKDOWN"]),
        }
        hist = df.iloc[:-horizon].copy()
        hist["REG_ABOVE_200"] = hist["Close"] > hist["EMA200"]
        hist["REG_EMA20_50"] = hist["EMA20"] > hist["EMA50"]
        hist["REG_RSI"] = hist["RSI14"].map(self._rsi_bucket)
        hist["REG_MACD"] = hist["MACD"] > hist["MACD_SIGNAL"]
        hist["REG_VOL"] = hist["REL_VOLUME"] >= 1.2
        hist["FWD_CLOSE"] = df["Close"].shift(-horizon).reindex(hist.index)
        hist["FWD_RETURN"] = hist["FWD_CLOSE"] / hist["Close"] - 1
        hist["FWD_MAX"] = pd.concat(
            [df["High"].shift(-i) for i in range(1, horizon + 1)], axis=1
        ).max(axis=1).reindex(hist.index)

        mask = (
            (hist["REG_ABOVE_200"] == regime["above_ema200"])
            & (hist["REG_EMA20_50"] == regime["ema20_above_ema50"])
            & (hist["REG_RSI"] == regime["rsi_bucket"])
            & (hist["REG_MACD"] == regime["macd_positive"])
        )
        if regime["high_relative_volume"]:
            mask &= hist["REG_VOL"]
        if regime["breakout"]:
            mask &= hist["BREAKOUT"]
        if regime["breakdown"]:
            mask &= hist["BREAKDOWN"]

        matched = hist.loc[mask].dropna(subset=["FWD_RETURN", "FWD_MAX"])
        return latest, regime, matched

    def analyze(
        self,
        symbol: str,
        horizon: int = 5,
        period: str = "5y",
        target_price: Optional[float] = None,
    ) -> AgentResult:
        result = super().analyze(symbol, horizon=horizon, period=period, target_price=None)
        raw = self.market_data.history(symbol, period=period)
        df = self.enrich(raw).dropna().copy()
        latest, regime, matched = self._matched_regimes(df, horizon)

        n = int(len(matched))
        bt = result.data.setdefault("backtest", {})
        bt["sample_size"] = n
        bt["horizon_trading_days"] = horizon
        bt["target_price"] = target_price
        bt["method"] = (
            "Frequência histórica de regimes técnicos comparáveis. Para um alvo de preço, cada ocorrência histórica "
            "é avaliada pelo mesmo retorno percentual exigido hoje, não pelo preço nominal do passado."
        )

        if n >= MIN_BACKTEST_SAMPLE:
            probability_up = float((matched["FWD_RETURN"] > 0).mean())
            bt["probability_positive_close"] = round(probability_up * 100, 2)
            bt["average_return_percent"] = round(float(matched["FWD_RETURN"].mean()) * 100, 3)
            bt["median_return_percent"] = round(float(matched["FWD_RETURN"].median()) * 100, 3)
            bt["confidence"] = "alta" if n >= 200 else "média" if n >= 75 else "baixa"
            if target_price is not None and target_price > 0:
                current_price = float(latest["Close"])
                required_return = target_price / current_price - 1
                historical_max_return = matched["FWD_MAX"] / matched["Close"] - 1
                bt["required_return_to_target_percent"] = round(required_return * 100, 3)
                bt["probability_reach_target_percent"] = round(
                    float((historical_max_return >= required_return).mean()) * 100, 2
                )
            else:
                bt["probability_reach_target_percent"] = None
        else:
            bt["probability_positive_close"] = None
            bt["probability_reach_target_percent"] = None
            bt["confidence"] = "insuficiente"
            result.warnings.append(
                f"O regime atual gerou apenas {n} ocorrências comparáveis após os filtros; percentagens preditivas foram suprimidas."
            )

        bias = result.data.get("bias")
        p_up = bt.get("probability_positive_close")
        if p_up is None:
            signal = "INSUFFICIENT_EVIDENCE"
        elif bias == "altista" and p_up >= 55:
            signal = "BULLISH_SETUP"
        elif bias == "baixista" and p_up <= 45:
            signal = "BEARISH_SETUP"
        else:
            signal = "WAIT_FOR_CONFIRMATION"

        result.data["decision_support"] = {
            "signal": signal,
            "note": (
                "Sinal quantitativo de apoio à decisão, não ordem de compra/venda. A percentagem é evidência histórica condicionada "
                "ao regime definido e pode falhar fora da amostra."
            ),
        }
        result.data["regime"] = regime
        return result


class SEIOrchestratorPro(SEIOrchestrator):
    """Production-oriented composition: LLM router + deterministic quantitative specialists."""

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.market = MarketDataAgent()
        self.technical = QuantTechnicalAnalysisAgent(self.market)
        self.statistics = StatisticsAgent(self.market)
        self.econometrics = EconometricsAgent(self.market)
        self.math = FinancialMathAgent()
        self.validator = ValidatorAgent()
        self.router = RichRouterAgent(self.llm)
