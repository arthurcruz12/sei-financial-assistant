from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

import pandas as pd

from macro_data import INEConnector, OfficialSeries, _period_to_timestamp, _request


MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def _ascii_lower(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def ine_period_to_timestamp(value: Any) -> pd.Timestamp:
    """Parse the human-readable period labels currently returned by INE."""
    raw = str(value).strip()
    text = _ascii_lower(raw)

    month_match = re.fullmatch(
        r"(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})",
        text,
    )
    if month_match:
        month = MONTHS_PT[month_match.group(1)]
        year = int(month_match.group(2))
        return pd.Period(f"{year}-{month:02d}", freq="M").end_time.normalize()

    quarter_match = re.fullmatch(
        r"([1-4])\s*(?:\.|o|º|\.?o)?\s*trimestre\s*(?:de\s*)?(\d{4})",
        text,
    )
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2))
        return pd.Period(f"{year}Q{quarter}", freq="Q").end_time.normalize()

    if re.fullmatch(r"\d{4}", text):
        return pd.Period(text, freq="Y").end_time.normalize()

    return _period_to_timestamp(raw)


def infer_ine_frequency(values) -> str:
    items = [str(v).strip() for v in values]
    if not items:
        return "unknown"
    text = _ascii_lower(items[0])
    if any(month in text for month in MONTHS_PT):
        return "M"
    if "trimestre" in text:
        return "Q"
    if re.fullmatch(r"\d{4}", text):
        return "A"
    # Fall back to timestamp spacing only when the label does not expose frequency.
    parsed = [ine_period_to_timestamp(v) for v in items[:3]]
    if len(parsed) >= 2:
        days = abs((parsed[0] - parsed[1]).days)
        if days <= 35:
            return "M"
        if days <= 100:
            return "Q"
        if days >= 300:
            return "A"
    return "unknown"


def _numeric_ine(values: pd.Series) -> pd.Series:
    # INE can return decimals as strings with Portuguese comma separators.
    normalized = values.astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
    normalized = normalized.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return pd.to_numeric(normalized, errors="coerce")


class CurrentINEConnector(INEConnector):
    """INE connector adapted to current human-readable Portuguese period labels."""

    def fetch(
        self,
        indicator: str,
        *,
        dimensions: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        lang: str = "PT",
    ) -> OfficialSeries:
        params: Dict[str, Any] = {"op": 2, "varcd": indicator, "lang": lang}
        if dimensions:
            params.update(dimensions)

        response = _request(self.DATA_URL, params=params)
        root, rows = self._extract_rows(response.json())
        if not rows:
            raise ValueError(f"INE não devolveu observações para o indicador {indicator}.")

        frame = pd.DataFrame(rows)
        if "valor" not in frame.columns:
            raise ValueError("Resposta INE sem campo 'valor'.")

        dimension_cols = [c for c in frame.columns if c not in {"period", "valor", "ind_string"}]
        code_cols = [c for c in dimension_cols if c.endswith("cod") or c.startswith("dim_") or c == "geocod"]
        if code_cols and len(frame[code_cols].drop_duplicates()) > 1:
            raise ValueError(
                f"INE devolveu múltiplas combinações para {indicator}. "
                "Use Dim1/Dim2/... para selecionar uma única série."
            )

        idx = pd.Index([ine_period_to_timestamp(v) for v in frame["period"]])
        series = pd.Series(_numeric_ine(frame["valor"]).to_numpy(), index=idx)
        title = name or root.get("IndicadorDsg") or f"INE {indicator}"
        frequency = infer_ine_frequency(frame["period"])

        return OfficialSeries(
            name=title,
            source="INE Portugal",
            series_id=indicator,
            frequency=frequency,
            unit=str(root.get("UnidadeMedida") or root.get("UnidadeMedidaDsg") or ""),
            data=series,
            source_url=response.url,
            metadata={
                "indicator": indicator,
                "last_update": root.get("DataUltimoAtualizacao") or root.get("DataUltimaAtualizacao"),
                "dimensions": dimensions or {},
                "metadata_url": f"{self.META_URL}?varcd={indicator}&lang={lang}",
            },
        ).clean()
