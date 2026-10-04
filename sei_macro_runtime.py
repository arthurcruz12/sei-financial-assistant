from __future__ import annotations

import re
from typing import List, Optional

from macro_analysis import MacroDataAgent, MacroEconometricsAgent
from macro_data import OfficialMacroHub, OfficialSeries
from sei_agents import AgentResult, RouterAgent
from sei_router import SEIChatOrchestrator


MACRO_STOP_TICKERS = {
    "PIB", "GDP", "INE", "ECB", "BCE", "FRED", "OECD", "EUROSTAT", "EURIBOR",
    "HICP", "IPC", "CPI", "FED", "OLS", "ADF", "HC3",
}

CROSS_TERMS = (
    "regress", "econometr", "correla", "relação", "relacao", "impacto", "explica",
    "cruza", "cruzar", "compara", "comparar", "granger", "efeito", "sensibilidade",
)

OECD_PT_UNEMPLOYMENT_FLOW = "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0"
OECD_PT_UNEMPLOYMENT_KEY = "PRT..._Z.Y._T.Y_GE15..Q"


class SEIOfficialMacroHub(OfficialMacroHub):
    """Current chat presets layered over the generic official connectors."""

    def get(self, alias: str, *, start: Optional[str] = None, end: Optional[str] = None) -> OfficialSeries:
        if alias == "pt_inflation_eurostat":
            # Eurostat replaced the legacy HICP structures in 2026 with prc_hicp_minr
            # using the ECOICOP-2018 dimension (`coicop18`).
            return self.eurostat.fetch(
                "prc_hicp_minr",
                filters={
                    "geo": "PT",
                    "freq": "M",
                    "unit": "RCH_A",
                    "coicop18": "CP00",
                },
                name="Inflação HICP Portugal - variação homóloga",
                start=start,
                end=end,
            )
        if alias == "pt_unemployment_oecd":
            return self.oecd.fetch(
                OECD_PT_UNEMPLOYMENT_FLOW,
                OECD_PT_UNEMPLOYMENT_KEY,
                name="Taxa de desemprego Portugal, 15+ anos, trimestral (OECD)",
                start=start,
                end=end,
            )
        return super().get(alias, start=start, end=end)


class MacroIntentParser:
    """Maps natural PT/EN macro vocabulary to official series aliases."""

    @staticmethod
    def _provider(message: str) -> Optional[str]:
        lower = message.lower()
        if "eurostat" in lower:
            return "eurostat"
        if "ine" in lower or "instituto nacional de estatística" in lower or "instituto nacional de estatistica" in lower:
            return "ine"
        if "fred" in lower or "st. louis fed" in lower:
            return "fred"
        if "oecd" in lower or "ocde" in lower:
            return "oecd"
        if "bce" in lower or "ecb" in lower:
            return "ecb"
        return None

    @staticmethod
    def _append_unique(items: List[str], value: str) -> None:
        if value not in items:
            items.append(value)

    def aliases(self, message: str) -> List[str]:
        lower = message.lower()
        provider = self._provider(message)
        aliases: List[str] = []

        if "euribor" in lower:
            if re.search(r"(?:12\s*(?:m|mes)|1\s*(?:ano|year))", lower):
                self._append_unique(aliases, "euribor12m")
            elif re.search(r"6\s*(?:m|mes)", lower):
                self._append_unique(aliases, "euribor6m")
            else:
                self._append_unique(aliases, "euribor3m")
        if any(term in lower for term in [
            "taxa do bce", "taxa bce", "juros bce", "ecb rate", "deposit facility",
            "taxa de depósito", "taxa de deposito",
        ]):
            self._append_unique(aliases, "ecb_deposit_rate")

        if any(term in lower for term in ["inflação", "inflacao", "ipc", "hicp", "consumer prices"]):
            if provider == "eurostat" or "harmoniz" in lower or "hicp" in lower:
                self._append_unique(aliases, "pt_inflation_eurostat")
            elif provider in {None, "ine"}:
                self._append_unique(aliases, "pt_inflation_ine")
        if any(term in lower for term in ["desemprego", "unemployment"]):
            if provider == "eurostat":
                self._append_unique(aliases, "pt_unemployment_eurostat")
            elif provider == "oecd":
                self._append_unique(aliases, "pt_unemployment_oecd")
            elif provider in {None, "ine"}:
                self._append_unique(aliases, "pt_unemployment_ine")
        if any(term in lower for term in ["pib", "gdp", "produto interno bruto"]):
            if provider == "eurostat":
                self._append_unique(aliases, "pt_gdp_qoq_eurostat")
            elif provider in {None, "ine"}:
                self._append_unique(aliases, "pt_gdp_yoy_ine")

        if provider == "fred" or any(term in lower for term in ["fed funds", "federal funds"]):
            if any(term in lower for term in ["fed funds", "federal funds", "taxa fed"]):
                self._append_unique(aliases, "fed_funds")
            if any(term in lower for term in ["desemprego usa", "us unemployment", "unemployment us"]):
                self._append_unique(aliases, "us_unemployment")
            if any(term in lower for term in ["pib usa", "us gdp", "gdp us"]):
                self._append_unique(aliases, "us_real_gdp")
            if any(term in lower for term in ["cpi usa", "us cpi", "inflação usa", "inflacao usa"]):
                self._append_unique(aliases, "us_inflation_cpi")

        return aliases

    @staticmethod
    def wants_cross_analysis(message: str) -> bool:
        lower = message.lower()
        return any(term in lower for term in CROSS_TERMS)

    @staticmethod
    def period(message: str) -> str:
        lower = message.lower()
        match = re.search(r"(\d{1,2})\s*(?:anos?|years?)", lower)
        if match:
            years = max(1, min(20, int(match.group(1))))
            return f"{years}y"
        return "10y"


class SEIMacroOrchestrator(SEIChatOrchestrator):
    """Single SEI chat with market agents plus official macro data/econometrics."""

    def __init__(self) -> None:
        super().__init__()
        self.macro_hub = SEIOfficialMacroHub()
        self.macro_data = MacroDataAgent(self.macro_hub)
        self.macro_econometrics = MacroEconometricsAgent(self.market, self.macro_hub)
        self.macro_parser = MacroIntentParser()

    def _market_symbols(self, message: str) -> List[str]:
        if hasattr(self.router, "_extract_symbols"):
            symbols = self.router._extract_symbols(message)
        else:
            symbols = RouterAgent.TICKER_RE.findall(message.upper())
        return [s for s in symbols if s not in MACRO_STOP_TICKERS]

    def chat(self, message: str, image_bytes: Optional[bytes] = None, mime_type: Optional[str] = None) -> List[AgentResult]:
        aliases = self.macro_parser.aliases(message)
        if not aliases:
            return super().chat(message, image_bytes=image_bytes, mime_type=mime_type)

        results: List[AgentResult] = []
        symbols = self._market_symbols(message)

        if image_bytes:
            vision = self.llm.inspect_chart_image(image_bytes, mime_type or "image/png", message)
            results.append(vision)
            if not symbols:
                symbols = self._market_symbols(vision.summary)[:1]

        try:
            if symbols and self.macro_parser.wants_cross_analysis(message):
                results.append(
                    self.macro_econometrics.market_vs_macro(
                        symbols[0],
                        aliases,
                        period=self.macro_parser.period(message),
                    )
                )
                return results

            if len(aliases) >= 2 and self.macro_parser.wants_cross_analysis(message):
                results.append(self.macro_econometrics.macro_vs_macro(aliases))
                return results

            results.append(self.macro_data.retrieve(aliases))
            return results
        except Exception as exc:
            results.append(
                AgentResult(
                    agent="macro_orchestrator",
                    summary=f"Não consegui concluir a consulta macroeconómica: {exc}",
                    warnings=[str(exc)],
                )
            )
            return results
