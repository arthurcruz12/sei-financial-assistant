"""Official Brazilian Central Bank SGS time-series connector (no scraping)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests

from macro_data import OfficialSeries, USER_AGENT

class BCBConnector:
    BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    PRESETS = {
        "br_selic_target": (432, "Meta Selic", "D", "% a.a."),
        "br_ipca": (433, "IPCA variação mensal", "M", "% a.m."),
        "br_usd_brl": (1, "Dólar comercial venda", "D", "BRL por USD"),
    }

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def fetch(self, code: int, *, name: str, frequency: str, unit: str,
              start: Optional[str] = None, end: Optional[str] = None) -> OfficialSeries:
        """Fetch a bounded SGS window. ISO dates required; no silent proxy/sample data."""
        today = date.today()
        end_date = date.fromisoformat(end) if end else today
        start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365 * 5)
        if start_date > end_date:
            raise ValueError("Data inicial posterior à data final.")
        if (end_date - start_date).days > 3650:
            raise ValueError("O SGS exige intervalos de até 10 anos; divida a consulta.")
        if end_date > today:
            raise ValueError("Não é permitido consultar observações futuras.")
        url = self.BASE.format(code=int(code))
        params = {
            "formato": "json",
            "dataInicial": start_date.strftime("%d/%m/%Y"),
            "dataFinal": end_date.strftime("%d/%m/%Y"),
        }
        response = self.session.get(url, params=params,
                                    headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise ValueError(f"SGS {code} sem observações no período solicitado.")
        frame = pd.DataFrame(payload)
        if not {"data", "valor"}.issubset(frame.columns):
            raise ValueError("Resposta SGS sem colunas data/valor.")
        index = pd.to_datetime(frame["data"], format="%d/%m/%Y", errors="raise")
        values = pd.to_numeric(frame["valor"].astype(str).str.replace(",", ".", regex=False),
                               errors="coerce")
        series = pd.Series(values.to_numpy(), index=index)
        if series.index.has_duplicates:
            raise ValueError("SGS devolveu datas duplicadas.")
        return OfficialSeries(
            name=name, source="Banco Central do Brasil (SGS)", series_id=f"SGS.{code}",
            frequency=frequency, unit=unit, data=series, source_url=response.url,
            metadata={"code": int(code), "requested_start": start_date.isoformat(),
                      "requested_end": end_date.isoformat()},
        ).clean()

    def preset(self, alias: str, *, start: Optional[str] = None,
               end: Optional[str] = None) -> OfficialSeries:
        code, name, frequency, unit = self.PRESETS[alias]
        return self.fetch(code, name=name, frequency=frequency, unit=unit,
                          start=start, end=end)
