from __future__ import annotations

import re
from typing import List

from sei_runtime import ASSET_ALIASES, RichRouterAgent, SEIOrchestratorPro


STOPWORDS = {
    "A", "O", "E", "EM", "DE", "DA", "DO", "DAS", "DOS", "NO", "NA", "NOS", "NAS",
    "PARA", "POR", "COM", "SEM", "QUE", "QUAL", "SE", "UM", "UMA", "AO", "AOS", "AS", "OS",
}

TECH_ACRONYMS = {
    "SEI", "RSI", "MACD", "EMA", "SMA", "ATR", "ADX", "VWAP", "OLS", "VAR", "VECM",
    "ARIMA", "SARIMA", "GARCH", "BCE", "ECB", "FED", "PIB", "GDP",
}


class BetterRouterAgent(RichRouterAgent):
    """Avoids treating normal Portuguese words/acronyms as market tickers."""

    def _extract_symbols(self, message: str) -> List[str]:
        symbols: List[str] = []
        lower = message.lower()

        # Known natural-language aliases have priority over raw ticker parsing.
        for alias, symbol in ASSET_ALIASES.items():
            if alias in lower:
                symbols.append(symbol)

        # Brazilian B3 shorthand: PETR4 -> PETR4.SA for Yahoo Finance.
        for token in re.findall(r"\b([A-Za-z]{4}\d{1,2})(?:\.SA)?\b", message):
            symbols.append(token.upper() + ".SA")

        # Explicit $ticker notation.
        for token in re.findall(r"(?<![A-Za-z0-9])\$([A-Za-z][A-Za-z0-9.-]{0,11})", message):
            symbols.append(token.upper())

        # Upper-case tickers typed explicitly by the user.
        for token in re.findall(r"\b[A-Z]{1,6}(?:-[A-Z]{2,4}|\.[A-Z]{1,4})?\b", message):
            if token in STOPWORDS or token in TECH_ACRONYMS:
                continue
            symbols.append(token)

        deduped: List[str] = []
        for symbol in symbols:
            if symbol not in deduped:
                deduped.append(symbol)
        return deduped


class SEIChatOrchestrator(SEIOrchestratorPro):
    def __init__(self) -> None:
        super().__init__()
        self.router = BetterRouterAgent(self.llm)
