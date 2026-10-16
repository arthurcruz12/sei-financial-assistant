"""SEI — dashboard em Streamlit com dados oficiais e análises reais."""
from __future__ import annotations

import mimetypes
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from sei_agents import result_to_markdown
from sei_dashboard import DISPLAY_SERIES, load_series, render_macro_dashboard
from sei_macro_runtime import SEIMacroOrchestrator

# Streamlit Community Cloud keeps credentials in App settings > Secrets.
# Do not require a local secrets.toml when the app runs in public-data-only mode.
for _secret_name in ("OPENAI_API_KEY", "OPENAI_MODEL", "FRED_API_KEY"):
    if not os.getenv(_secret_name):
        try:
            _secret_value = st.secrets.get(_secret_name)
            if _secret_value:
                os.environ[_secret_name] = str(_secret_value)
        except (FileNotFoundError, KeyError):
            pass

st.set_page_config(page_title="SEI — Inteligência Económica", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --sei-teal:#008985; --sei-ink:#102d3d; }
.stApp { background-color:#f6fafb;
 background-image:linear-gradient(#eef4f5 1px,transparent 1px),linear-gradient(90deg,#eef4f5 1px,transparent 1px);
 background-size:27px 27px; }
[data-testid="stSidebar"] { background:#eef5f6!important; border-right:1px solid #dae7e9; }
[data-testid="stSidebar"] > div {background:#eef5f6!important;}
.block-container { padding-top:2.4rem; padding-bottom:2rem; max-width:1400px; }
[data-testid="stVerticalBlockBorderWrapper"]:has(>div[data-testid="stVerticalBlock"]) {border-radius:16px;}
div[data-testid="stVerticalBlockBorderWrapper"][data-testid] > div[style*="border"] {border-radius:16px!important;}
[data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stLineChart"]) {
 border:1px solid #dfe9eb!important; background:white!important; box-shadow:0 3px 14px rgba(15,55,72,.035);}
[data-testid="stVerticalBlockBorderWrapper"]:has(.sei-eyebrow) {
 border:1px solid #dce7e9!important; background:#fff!important; border-radius:16px!important;
 padding:10px 14px!important; box-shadow:0 4px 16px rgba(11,50,65,.045);}
[data-testid="stSidebar"] .stButton>button {
 border:0!important; background:transparent!important; color:#385b6b!important;
 text-align:left!important; justify-content:flex-start!important; font-size:14px!important;
 box-shadow:none!important; border-radius:9px!important; padding:8px 13px!important;
 min-height:42px!important; font-weight:500!important;}
[data-testid="stSidebar"] .stButton>button:hover {background:#deeeee!important;color:#006e76!important;}
[data-testid="stSidebar"] .stButton>button[kind="primary"] {
 background:#d7eded!important;color:#007c83!important;font-weight:700!important;}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {
 background:#008985!important; border:1px solid #008985!important; color:#fff!important;}
.stButton>button[kind="secondary"],.stDownloadButton>button {
 background:#fff!important; color:#20455a!important; border:1px solid #d8e4e7!important;
 border-radius:9px!important;}
.stButton>button:hover,.stDownloadButton>button:hover {border-color:#008985!important;color:#007c83!important;}
[data-testid="stSelectbox"] [data-baseweb="select"],[data-testid="stMultiSelect"] [data-baseweb="select"] {
 background:#fff!important; color:#123249!important; border-radius:9px!important;}
[data-testid="stSegmentedControl"] button {background:#fff!important;color:#315568!important;border-color:#d9e5e8!important;}
[data-testid="stSegmentedControl"] button[aria-checked="true"] {background:#ddf0ee!important;color:#007e80!important;}
[data-testid="stMetricValue"] {color:#008985!important;}
[data-testid="stChart"] {border-radius:12px;overflow:hidden;}
h1,h2,h3 { color:#102d3d!important; letter-spacing:-.025em; }
p, label {color:#3b6273;}
.sei-eyebrow {font-size:10px;letter-spacing:.16em;font-weight:780;color:#4e8190;text-transform:uppercase;}
.sei-title {font-size:23px;font-weight:760;color:#0b2c3c;margin:10px 0 8px;}
.sei-body {color:#567487;font-size:14px;line-height:1.75;}
.sei-muted {font-size:12px;color:#678798;}
.sei-brand {font-size:29px;font-weight:800;letter-spacing:-1px;color:#0a3544;}
.sei-foot {font-size:12px;color:#78919c;padding-top:18px;border-top:1px solid #dce7e9;}
@media (max-width:850px) {.block-container{padding:1.25rem .75rem!important}.sei-title{font-size:20px}}

/* Reference fidelity: light side navigation and equal-height white cards */
header[data-testid="stHeader"] {background:transparent!important;}
[data-testid="stSidebar"] {min-width:265px!important;max-width:265px!important;}
[data-testid="stSidebar"] .stButton>button[kind="secondary"],
[data-testid="stSidebar"] .stButton>button[kind="primary"] {
 background:transparent!important;border:0!important;color:#395e70!important;
 min-height:37px!important;box-shadow:none!important;margin:0!important;
 padding:7px 13px!important;justify-content:flex-start!important;font-weight:500!important;}
[data-testid="stSidebar"] .stButton>button[kind="primary"] {
 background:#dcefee!important;color:#007d80!important;font-weight:700!important;}
[data-testid="stSidebar"] .stButton>button[kind="secondary"]:hover {background:#e0eeee!important;color:#007b80!important;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.23rem!important;}
[data-testid="stSidebar"] hr {border-color:#dce7e9!important;margin:9px 0!important;}
.sei-logo {display:inline-flex;align-items:center;justify-content:center;color:#008985;
 font-weight:650;background:#dcefee;border-radius:13px;width:46px;height:46px;margin-right:7px;}
.sei-brand {display:flex;align-items:center;}
.sei-sidebar-foot {color:#3e6b7a;font-size:12px;line-height:1.8;border-top:1px solid #d5e4e7;padding-top:15px;}
.sei-sidebar-foot small {font-size:10px;color:#648596;}
.block-container {padding-top:1.3rem!important; max-width:1120px!important;}
[data-testid="stVerticalBlockBorderWrapper"]:has(.sei-eyebrow){
 box-shadow:0 1px 3px rgba(19,54,72,.04)!important;
 padding:18px 22px!important;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(.sei-eyebrow) [data-testid="stVerticalBlock"] {gap:.6rem;}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stLineChart"] {background:#fff!important;}
[data-testid="stSegmentedControl"] button {border-radius:6px!important;}
.sei-stat {display:flex;justify-content:space-between;gap:16px;font-size:13px;color:#658391;
 margin-top:13px;padding:5px 0;}
.sei-stat b {color:#008985;}
.sei-title {font-size:22px;line-height:1.35;}
[data-testid="stDownloadButton"] button {border:0!important;background:transparent!important;color:#008985!important;}
@media(min-width:1280px){.block-container {margin-left:auto!important;margin-right:auto!important;}}
</style>
""", unsafe_allow_html=True)

PAGES = ["Visão geral","Indicadores","Mercados globais","Radar de crise","Liquidez global","Previsões","Cenários",
         "Analisar investimento","Watchlist","Portfolio Builder","Assistente SEI","O meu perfil","Histórico","Fontes e metodologia"]
ICONS = ["▦","⌁","◎","◉","▤","↗","▱","⌕","☆","▣","▢","☷","◷","♢"]
if "page" not in st.session_state: st.session_state.page = "Visão geral"
if "messages" not in st.session_state: st.session_state.messages = []
if "orchestrator" not in st.session_state: st.session_state.orchestrator = SEIMacroOrchestrator()

with st.sidebar:
    st.markdown('<div class="sei-brand"><span class="sei-logo">∿</span> SEI</div><div class="sei-eyebrow" style="padding-left:56px">ECONOMIC INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown("<div style=\"height:25px\"></div>", unsafe_allow_html=True)
    st.markdown('<div class="sei-eyebrow">O SEU ESPAÇO DE ANÁLISE</div>',unsafe_allow_html=True)
    for i,page in enumerate(PAGES):
        if i in (7,11): st.divider()
        if st.button(f"{ICONS[i]}  {page}",key=f"nav_{i}",use_container_width=True,
                     type="primary" if st.session_state.page==page else "secondary"):
            st.session_state.page=page
            st.rerun()
    st.divider()
    st.markdown('<div class="sei-sidebar-foot">♢ &nbsp; Inteligência com transparência<br><small>Fontes identificadas. Limites claros.</small></div>', unsafe_allow_html=True)

def home():
    left,right=st.columns([1.62,1],gap="medium")
    start=(date.today()-timedelta(days=365*3)).isoformat()
    end=date.today().isoformat()
    with left:
        with st.container(border=True, height=530):
            st.markdown('<div class="sei-eyebrow">EVOLUÇÃO OBSERVADA</div>',unsafe_allow_html=True)
            st.markdown('<div class="sei-title">Evolução dos indicadores</div>',unsafe_allow_html=True)
            alias=st.selectbox("Série a visualizar",["euribor3m","pt_inflation_ine","br_ipca","br_usd_brl","br_selic_target"],
                format_func=lambda a: next((k for k,v in DISPLAY_SERIES.items() if v==a),a),
                label_visibility="collapsed")
            n=st.segmented_control("Observações",[30,90,180],default=90,format_func=lambda x:f"{x} obs.",label_visibility="collapsed")
            try:
                payload=load_series(alias,start,end)
                df=payload["data"].dropna(subset=["value"]).sort_values("date").tail(n or 90)
                if len(df):
                    st.line_chart(df.set_index("date")["value"],height=245,color="#008D91")
                    st.caption(f"Última observação: {df.iloc[-1]['date'].date()} · {float(df.iloc[-1]['value']):.4f} {payload['unit']}")
                    st.markdown(f"**Fonte:** [{payload['source']}]({payload['source_url']}) · Série {payload['series_id']}")
                    st.download_button("↓ Exportar série (CSV)",df.to_csv(index=False).encode("utf-8"),"sei_serie.csv","text/csv")
                else: st.info("A aguardar observações da fonte — sem dados no intervalo.")
            except Exception as exc:
                st.warning("Fonte indisponível neste momento.")
                st.caption(str(exc))
            st.caption("Dados históricos · sem interpolação de lacunas")
    with right:
        with st.container(border=True):
            st.markdown('<div class="sei-eyebrow">♢ QUALIDADE DA INFORMAÇÃO</div>',unsafe_allow_html=True)
            st.markdown('<div class="sei-title">Uma decisão começa na qualidade da fonte.</div>',unsafe_allow_html=True)
            st.markdown('<p class="sei-body">Cada indicador preserva a origem, a série e a data de referência. Ausência de dados nunca é substituída por valores inventados.</p>',unsafe_allow_html=True)
            st.markdown('<div class="sei-stat"><span>Séries disponíveis no painel</span><b>5</b></div><div class="sei-stat"><span>Fonte identificada</span><b>✓</b></div>',unsafe_allow_html=True)
            st.write("")
            if st.button("Explorar fontes ↗",use_container_width=True,type="primary"):
                st.session_state.page="Fontes e metodologia"
                st.rerun()
    lowleft,lowright=st.columns([1.62,1],gap="medium")
    with lowleft:
        with st.container(border=True):
            st.subheader("Na origem da informação")
            st.markdown('<p class="sei-body">Consulta a instituições oficiais e respetivas séries históricas verificáveis.</p>',unsafe_allow_html=True)
            st.markdown("[Consultar o portal do BCE ↗](https://data.ecb.europa.eu/)")
    with lowright:
        with st.container(border=True):
            st.subheader("Da informação à decisão")
            for title,detail,page in [
                ("01 · Defina o seu contexto","Perfil, horizonte e orçamento.","O meu perfil"),
                ("02 · Explore outros cenários","Torne os pressupostos explícitos.","Cenários"),
                ("03 · Simule uma carteira","Compare distribuições de capital.","Portfolio Builder")]:
                if st.button(title + "  ›",use_container_width=True,key=page):
                    st.session_state.page=page
                    st.rerun()
                st.caption(detail)
    st.markdown('<div class="sei-foot">⌁ SEI · Inteligência económica, com contexto. &nbsp;&nbsp; Investigação e simulação. Não constitui aconselhamento financeiro.</div>',unsafe_allow_html=True)

def assistant():
    st.markdown('<div class="sei-eyebrow">ASSISTENTE SEI</div><div class="sei-title">Análise económica quantitativa</div>',unsafe_allow_html=True)
    uploaded=st.file_uploader("Gráfico ou screenshot (opcional)",type=["png","jpg","jpeg","webp"])
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    prompt=st.chat_input("Pergunte sobre mercados, regressões, indicadores ou risco…")
    if prompt:
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.write(prompt)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Consultando fontes e calculando…"):
                    results=st.session_state.orchestrator.chat(prompt,
                        image_bytes=uploaded.getvalue() if uploaded else None,
                        mime_type=mimetypes.guess_type(uploaded.name)[0] if uploaded else None)
                answer="\n\n---\n\n".join(result_to_markdown(r) for r in results)
            except Exception as exc:
                answer=f"Não foi possível concluir a análise: {exc}"
            st.markdown(answer)
        st.session_state.messages.append({"role":"assistant","content":answer})

page=st.session_state.page
if page=="Visão geral":
    home()
elif page in ("Indicadores","Mercados globais","Radar de crise","Liquidez global","Previsões","Cenários","Analisar investimento"):
    st.markdown(f'<div class="sei-eyebrow">INTELIGÊNCIA ECONÓMICA</div><div class="sei-title">{page}</div>',unsafe_allow_html=True)
    render_macro_dashboard()
    if page in ("Previsões","Radar de crise"):
        st.info("Os indicadores são observados; previsões e sinais de risco apenas serão apresentados após validação estatística própria.")
elif page=="Assistente SEI":
    assistant()
elif page=="Fontes e metodologia":
    st.title("Fontes e metodologia")
    st.write("Séries oficiais do BCE, Eurostat, INE, BCB e outros fornecedores descritos nas observações. Regressões estimadas em Python com validação de amostra e erros-padrão HC3.")
    render_macro_dashboard()
elif page in ("Watchlist","Portfolio Builder","O meu perfil","Histórico"):
    st.title(page)
    st.info("Este módulo ainda não tem persistência funcional nesta versão publicada. Sem demonstrações fictícias.")
    if st.button("Abrir o assistente SEI"):
        st.session_state.page="Assistente SEI"
        st.rerun()
