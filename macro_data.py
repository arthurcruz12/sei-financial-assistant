from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import requests


DEFAULT_TIMEOUT = 30
USER_AGENT = "SEI-Quantitative-Assistant/0.3 (+https://github.com/arthurcruz12/sei-financial-assistant)"


@dataclass
class OfficialSeries:
    name: str
    source: str
    series_id: str
    frequency: str
    unit: str
    data: pd.Series
    source_url: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def clean(self) -> "OfficialSeries":
        series = pd.to_numeric(self.data, errors="coerce").dropna().sort_index()
        series.name = self.name
        self.data = series
        return self

    def latest(self) -> Dict[str, Any]:
        clean = self.clean().data
        if clean.empty:
            return {"date": None, "value": None}
        return {"date": str(clean.index[-1].date()), "value": float(clean.iloc[-1])}


def _request(url: str, *, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> requests.Response:
    merged_headers = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)
    response = requests.get(url, params=params, headers=merged_headers, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response


def _period_to_timestamp(value: Any) -> pd.Timestamp:
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-Q[1-4]", text):
        return pd.Period(text, freq="Q").end_time.normalize()
    if re.fullmatch(r"\d{4}-M\d{2}", text):
        year, month = text.split("-M")
        return pd.Period(f"{year}-{month}", freq="M").end_time.normalize()
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return pd.Period(text, freq="M").end_time.normalize()
    if re.fullmatch(r"\d{4}", text):
        return pd.Period(text, freq="Y").end_time.normalize()
    return pd.to_datetime(text).normalize()


def _infer_frequency(values: Iterable[Any]) -> str:
    values = [str(v) for v in values]
    if not values:
        return "unknown"
    sample = values[0]
    if "Q" in sample:
        return "Q"
    if re.fullmatch(r"\d{4}-(?:M)?\d{2}", sample):
        return "M"
    if re.fullmatch(r"\d{4}", sample):
        return "A"
    return "D"


class ECBConnector:
    BASE = "https://data-api.ecb.europa.eu/service/data"

    PRESETS = {
        "euribor3m": ("FM", "M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA", "Euribor 3 meses"),
        "euribor6m": ("FM", "M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA", "Euribor 6 meses"),
        "euribor12m": ("FM", "M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA", "Euribor 12 meses"),
        "ecb_deposit_rate": ("FM", "B.U2.EUR.4F.KR.DFR.LEV", "Taxa da facilidade permanente de depósito do BCE"),
    }

    def fetch(
        self,
        flow: str,
        key: str,
        *,
        name: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> OfficialSeries:
        url = f"{self.BASE}/{flow}/{key}"
        params: Dict[str, Any] = {"format": "csvdata"}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end
        response = _request(url, params=params, headers={"Accept": "text/csv"})
        frame = pd.read_csv(io.StringIO(response.text))
        if frame.empty or "TIME_PERIOD" not in frame.columns or "OBS_VALUE" not in frame.columns:
            raise ValueError(f"ECB não devolveu observações para {flow}/{key}.")
        if frame["TIME_PERIOD"].duplicated().any():
            raise ValueError("A consulta ECB devolveu múltiplas séries. Use uma series key mais específica.")
        idx = pd.Index([_period_to_timestamp(v) for v in frame["TIME_PERIOD"]])
        series = pd.Series(pd.to_numeric(frame["OBS_VALUE"], errors="coerce").to_numpy(), index=idx)
        frequency = str(frame["FREQ"].iloc[0]) if "FREQ" in frame.columns else _infer_frequency(frame["TIME_PERIOD"])
        unit = str(frame["UNIT"].iloc[0]) if "UNIT" in frame.columns else ""
        title = name or (str(frame["TITLE_COMPL"].iloc[0]) if "TITLE_COMPL" in frame.columns else f"ECB {flow}/{key}")
        return OfficialSeries(
            name=title,
            source="ECB",
            series_id=f"{flow}.{key}",
            frequency=frequency,
            unit=unit,
            data=series,
            source_url=response.url,
            metadata={"flow": flow, "key": key},
        ).clean()

    def preset(self, alias: str, *, start: Optional[str] = None, end: Optional[str] = None) -> OfficialSeries:
        flow, key, name = self.PRESETS[alias]
        return self.fetch(flow, key, name=name, start=start, end=end)


class EurostatConnector:
    BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

    PRESETS = {
        "pt_inflation_eurostat": (
            "teicp000",
            {"geo": "PT", "unit": "RCH_A"},
            "Inflação HICP Portugal - variação homóloga",
        ),
        "pt_unemployment_eurostat": (
            "une_rt_m",
            {"geo": "PT", "freq": "M", "s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT", "sex": "T"},
            "Taxa de desemprego Portugal - ajustada sazonalmente",
        ),
        "pt_gdp_qoq_eurostat": (
            "teina011",
            {"geo": "PT", "unit": "CLV_PCH_PRE"},
            "PIB real Portugal - variação trimestral",
        ),
    }

    @staticmethod
    def _dimension_codes(payload: Dict[str, Any], dim: str) -> list[str]:
        category = payload["dimension"][dim]["category"]
        index = category.get("index", {})
        if isinstance(index, dict):
            return [k for k, _ in sorted(index.items(), key=lambda item: item[1])]
        if isinstance(index, list):
            return list(index)
        labels = category.get("label", {})
        return list(labels.keys())

    @classmethod
    def _flatten_jsonstat(cls, payload: Dict[str, Any]) -> pd.DataFrame:
        dims = payload.get("id") or []
        sizes = payload.get("size") or []
        if not dims or not sizes:
            raise ValueError("Resposta Eurostat sem estrutura JSON-stat esperada.")
        codes_by_dim = [cls._dimension_codes(payload, dim) for dim in dims]
        values = payload.get("value", {})
        rows = []
        for linear_key, raw_value in values.items():
            linear = int(linear_key)
            coords = []
            remainder = linear
            for size in reversed(sizes):
                coords.append(remainder % int(size))
                remainder //= int(size)
            coords.reverse()
            row = {dim: codes_by_dim[i][coords[i]] for i, dim in enumerate(dims)}
            row["OBS_VALUE"] = raw_value
            rows.append(row)
        return pd.DataFrame(rows)

    def fetch(
        self,
        dataset: str,
        *,
        filters: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> OfficialSeries:
        url = f"{self.BASE}/{dataset}"
        params: Dict[str, Any] = {"format": "JSON", "lang": "en"}
        if filters:
            params.update(filters)
        if start:
            params["sinceTimePeriod"] = start
        if end:
            params["untilTimePeriod"] = end
        response = _request(url, params=params)
        payload = response.json()
        frame = self._flatten_jsonstat(payload)
        if frame.empty or "time" not in frame.columns:
            raise ValueError(f"Eurostat não devolveu observações para {dataset}.")
        non_time = [c for c in frame.columns if c not in {"time", "OBS_VALUE"}]
        distinct = frame[non_time].drop_duplicates() if non_time else pd.DataFrame([{}])
        if len(distinct) > 1:
            raise ValueError(
                f"Eurostat devolveu {len(distinct)} combinações de série para {dataset}. "
                "Adicione filtros até restar uma única série."
            )
        idx = pd.Index([_period_to_timestamp(v) for v in frame["time"]])
        series = pd.Series(pd.to_numeric(frame["OBS_VALUE"], errors="coerce").to_numpy(), index=idx)
        frequency = str(frame["freq"].iloc[0]) if "freq" in frame.columns else _infer_frequency(frame["time"])
        unit = str(frame["unit"].iloc[0]) if "unit" in frame.columns else ""
        return OfficialSeries(
            name=name or f"Eurostat {dataset}",
            source="Eurostat",
            series_id=dataset,
            frequency=frequency,
            unit=unit,
            data=series,
            source_url=response.url,
            metadata={"dataset": dataset, "filters": filters or {}},
        ).clean()

    def preset(self, alias: str, *, start: Optional[str] = None, end: Optional[str] = None) -> OfficialSeries:
        dataset, filters, name = self.PRESETS[alias]
        return self.fetch(dataset, filters=filters, name=name, start=start, end=end)


class INEConnector:
    DATA_URL = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
    META_URL = "https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp"

    PRESETS = {
        "pt_inflation_ine": ("0014663", {"Dim2": "PT", "Dim3": "T"}, "IPC Portugal - variação homóloga"),
        "pt_gdp_yoy_ine": ("0013431", {"Dim2": "PT"}, "PIB real Portugal - variação homóloga"),
        "pt_unemployment_ine": ("0012136", {"Dim2": "PT", "Dim3": "T"}, "Taxa de desemprego Portugal"),
    }

    @staticmethod
    def _extract_rows(payload: Any) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
        root = payload[0] if isinstance(payload, list) else payload
        if not isinstance(root, dict):
            raise ValueError("Resposta INE em formato inesperado.")
        dados = root.get("Dados") or {}
        rows: list[Dict[str, Any]] = []
        if isinstance(dados, dict):
            for period, records in dados.items():
                if isinstance(records, dict):
                    records = [records]
                for record in records or []:
                    if isinstance(record, dict):
                        item = dict(record)
                        item["period"] = period
                        rows.append(item)
        return root, rows

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
        idx = pd.Index([_period_to_timestamp(v.replace("S3A", "") if str(v).startswith("S3A") else v) for v in frame["period"]])
        series = pd.Series(pd.to_numeric(frame["valor"], errors="coerce").to_numpy(), index=idx)
        title = name or root.get("IndicadorDsg") or f"INE {indicator}"
        frequency = _infer_frequency(frame["period"])
        return OfficialSeries(
            name=title,
            source="INE Portugal",
            series_id=indicator,
            frequency=frequency,
            unit="",
            data=series,
            source_url=response.url,
            metadata={
                "indicator": indicator,
                "last_update": root.get("DataUltimoAtualizacao") or root.get("DataUltimaAtualizacao"),
                "dimensions": dimensions or {},
                "metadata_url": f"{self.META_URL}?varcd={indicator}&lang={lang}",
            },
        ).clean()

    def preset(self, alias: str) -> OfficialSeries:
        indicator, dimensions, name = self.PRESETS[alias]
        return self.fetch(indicator, dimensions=dimensions, name=name)


class FREDConnector:
    BASE = "https://api.stlouisfed.org/fred/series/observations"

    PRESETS = {
        "us_inflation_cpi": ("CPIAUCSL", "US CPI index"),
        "us_unemployment": ("UNRATE", "US unemployment rate"),
        "us_real_gdp": ("GDPC1", "US real GDP"),
        "fed_funds": ("FEDFUNDS", "Effective federal funds rate"),
    }

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("FRED_API_KEY")

    def fetch(self, series_id: str, *, name: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> OfficialSeries:
        if not self.api_key:
            raise ValueError("FRED requer FRED_API_KEY no ambiente.")
        params: Dict[str, Any] = {"series_id": series_id, "api_key": self.api_key, "file_type": "json"}
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        response = _request(self.BASE, params=params)
        payload = response.json()
        observations = payload.get("observations") or []
        if not observations:
            raise ValueError(f"FRED não devolveu observações para {series_id}.")
        frame = pd.DataFrame(observations)
        idx = pd.to_datetime(frame["date"])
        values = pd.to_numeric(frame["value"].replace(".", pd.NA), errors="coerce")
        series = pd.Series(values.to_numpy(), index=idx)
        return OfficialSeries(
            name=name or f"FRED {series_id}",
            source="FRED",
            series_id=series_id,
            frequency=_infer_frequency(frame["date"]),
            unit="",
            data=series,
            source_url=response.url,
            metadata={"realtime_start": payload.get("realtime_start"), "realtime_end": payload.get("realtime_end")},
        ).clean()

    def preset(self, alias: str, *, start: Optional[str] = None, end: Optional[str] = None) -> OfficialSeries:
        series_id, name = self.PRESETS[alias]
        return self.fetch(series_id, name=name, start=start, end=end)


class OECDConnector:
    BASE = "https://sdmx.oecd.org/public/rest/data"

    def fetch(
        self,
        flow_ref: str,
        key: str = "all",
        *,
        name: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        filters: Optional[Dict[str, str]] = None,
    ) -> OfficialSeries:
        url = f"{self.BASE}/{flow_ref}/{key}"
        params: Dict[str, Any] = {"dimensionAtObservation": "AllDimensions", "format": "csvfilewithlabels"}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end
        if filters:
            params.update(filters)
        response = _request(url, params=params)
        frame = pd.read_csv(io.StringIO(response.text))
        time_col = "TIME_PERIOD" if "TIME_PERIOD" in frame.columns else "Time period"
        value_col = "OBS_VALUE" if "OBS_VALUE" in frame.columns else "Observation value"
        if frame.empty or time_col not in frame.columns or value_col not in frame.columns:
            raise ValueError("OECD não devolveu dados tabulares no formato esperado.")
        non_measure = {time_col, value_col, "OBS_STATUS", "Observation status"}
        candidate_id_cols = [c for c in frame.columns if c not in non_measure and not str(c).endswith("_LABEL")]
        if candidate_id_cols and len(frame[candidate_id_cols].drop_duplicates()) > 1:
            raise ValueError("OECD devolveu múltiplas séries. Refine a key SDMX no Data Explorer/API query builder.")
        idx = pd.Index([_period_to_timestamp(v) for v in frame[time_col]])
        series = pd.Series(pd.to_numeric(frame[value_col], errors="coerce").to_numpy(), index=idx)
        freq_col = "FREQ" if "FREQ" in frame.columns else None
        frequency = str(frame[freq_col].iloc[0]) if freq_col else _infer_frequency(frame[time_col])
        unit = str(frame["UNIT_MEASURE"].iloc[0]) if "UNIT_MEASURE" in frame.columns else ""
        return OfficialSeries(
            name=name or f"OECD {flow_ref}",
            source="OECD",
            series_id=f"{flow_ref}/{key}",
            frequency=frequency,
            unit=unit,
            data=series,
            source_url=response.url,
            metadata={"flow_ref": flow_ref, "key": key},
        ).clean()


class OfficialMacroHub:
    """One entry point for official macroeconomic time series."""

    def __init__(self) -> None:
        self.ecb = ECBConnector()
        self.eurostat = EurostatConnector()
        self.ine = INEConnector()
        self.fred = FREDConnector()
        self.oecd = OECDConnector()

    @property
    def aliases(self) -> set[str]:
        return set(ECBConnector.PRESETS) | set(EurostatConnector.PRESETS) | set(INEConnector.PRESETS) | set(FREDConnector.PRESETS)

    def get(self, alias: str, *, start: Optional[str] = None, end: Optional[str] = None) -> OfficialSeries:
        if alias in ECBConnector.PRESETS:
            return self.ecb.preset(alias, start=start, end=end)
        if alias in EurostatConnector.PRESETS:
            return self.eurostat.preset(alias, start=start, end=end)
        if alias in INEConnector.PRESETS:
            return self.ine.preset(alias)
        if alias in FREDConnector.PRESETS:
            return self.fred.preset(alias, start=start, end=end)
        raise KeyError(f"Série macro não registada: {alias}")
