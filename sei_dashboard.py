"""Visual analytics for verified macro series in the existing Streamlit SEI."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from macro_analysis import MacroEconometricsAgent
from quantitative import ols_diagnostics
from sei_macro_runtime import SEIOfficialMacroHub

DISPLAY_SERIES = {
    "Inflação Portugal (INE)": "pt_inflation_ine",
    "Euribor 3 meses (BCE)": "euribor3m",
    "Selic meta (BCB)": "br_selic_target",
    "IPCA Brasil (BCB)": "br_ipca",
    "USD/BRL (BCB)": "br_usd_brl",
}

@st.cache_data(ttl=3600, show_spinner=False)
def load_series(alias: str, start: str, end: str) -> dict:
    s = SEIOfficialMacroHub().get(alias, start=start, end=end)
    frame = pd.DataFrame({"date": s.data.index, "value": s.data.to_numpy()})
    return {"data": frame, "name": s.name, "source": s.source,
            "unit": s.unit, "source_url": s.source_url,
            "series_id": s.series_id, "frequency": s.frequency}

def render_macro_dashboard() -> None:
    st.subheader("Indicadores económicos — observações reais")
    st.caption("Sem dados simulados. Dados em cache até 1 hora; fontes e períodos apresentados por série.")
    options = list(DISPLAY_SERIES)
    selection = st.multiselect("Séries oficiais", options, default=options[:2])
    start = st.date_input("Início", value=pd.Timestamp("2021-01-01").date(), key="macro_start")
    end = st.date_input("Fim", value=pd.Timestamp.today().date(), key="macro_end")
    if start > end:
        st.error("O início deve ser anterior ou igual ao fim.")
        return
    available = {}
    for label in selection:
        alias = DISPLAY_SERIES[label]
        try:
            payload = load_series(alias, start.isoformat(), end.isoformat())
            df = payload["data"]
            if df.empty:
                st.warning(f"{label}: sem observações para este intervalo.")
                continue
            available[alias] = payload
            with st.expander(f"{label} — {len(df)} observações", expanded=True):
                st.line_chart(df.set_index("date")["value"], x_label="Data", y_label=payload["unit"] or "Valor")
                st.caption(f"Fonte: {payload['source']} · Série: {payload['series_id']} · Frequência: {payload['frequency']}")
                st.markdown(f"[Consultar observações na fonte]({payload['source_url']})")
                st.dataframe(df.sort_values("date", ascending=False), hide_index=True)
        except Exception as exc:
            st.error(f"{label}: não foi possível obter dados oficiais: {exc}")
    st.caption(f"{len(available)} de {len(selection)} séries selecionadas com observações disponíveis.")

    st.divider()
    st.subheader("Econometria — séries oficiais")
    if len(available) < 2:
        st.info("Selecione pelo menos duas séries disponíveis para calcular uma regressão.")
        return
    names = list(available)
    dependent = st.selectbox("Variável dependente", names, format_func=lambda a: next(k for k,v in DISPLAY_SERIES.items() if v == a))
    explanatory = st.multiselect("Variáveis explicativas", [a for a in names if a != dependent],
                                  default=[a for a in names if a != dependent][:1],
                                  format_func=lambda a: next(k for k,v in DISPLAY_SERIES.items() if v == a))
    if st.button("Calcular regressão com dados reais") and explanatory:
        try:
            from macro_analysis import _coarsest_frequency, _resample_macro
            hub = SEIOfficialMacroHub()
            aliases = [dependent, *explanatory]
            series = [hub.get(alias, start=start.isoformat(), end=end.isoformat()) for alias in aliases]
            freq = _coarsest_frequency(series)
            panel = pd.concat(
                [_resample_macro(s.data, freq).rename(alias) for alias, s in zip(aliases, series)],
                axis=1, join="inner")
            result = ols_diagnostics(panel, dependent, explanatory)
            st.metric("R²", round(result["r_squared"], 4))
            st.metric("Observações alinhadas", result["nobs"])
            st.write("Frequência comum", freq)
            st.dataframe(pd.DataFrame(result["coefficients"]).T, use_container_width=True)
            st.write("Correlação", pd.DataFrame(result["correlation"]))
            st.write("VIF", result["vif"])
            st.write("ADF (p-valores)", result["adf_p_values"])
            st.write("Breusch-Pagan (p-valor)", result["breusch_pagan_p_value"])
            st.write("Breusch-Godfrey (p-valor)", result["breusch_godfrey_p_value"])
            st.caption(result["method"] + " " + result["caution"])
            for s in series:
                st.caption(f"{s.source} · {s.series_id}: {s.source_url}")
        except Exception as exc:
            st.error(f"Não foi possível estimar a regressão: {exc}")
