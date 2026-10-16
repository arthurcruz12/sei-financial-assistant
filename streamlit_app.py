"""SEI — dashboard em Streamlit com dados oficiais e análises reais."""
from __future__ import annotations

import mimetypes
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from sei_agents import result_to_markdown
from sei_dashboard import DISPLAY_SERIES, load_series, render_macro_dashboard
from sei_macro_runtime import SEIMacroOrchestrator

st.set_page_config(page_title="SEI — Inteligência Económica", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --sei-teal:#008985; --sei-ink:#09243a; }
.stApp { color:var(--sei-ink); background-color:#f6fafb;
 background-image:linear-gradient(#eaf2f3 1px,transparent 1px),linear-gradient(90deg,#eaf2f3 1px,transparent 1px);
 background-size:26px 26px; }
[data-testid="stSidebar"] { background:#edf4f5; border-right:1px solid #dae5e8; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#3a6572; }
.block-container { padding-top:2rem; max-width:1450px; }
div[data-testid="stVerticalBlockBorderWrapper"] > div { border-color:#dce7e9 !important; border-radius:14px !important; background:#fff; }
.stButton > button[kind="primary"] { background:#008985; border-color:#008985; }
h1,h2,h3 { color:#0b273b !important; letter-spacing:-.02em; }
[data-testid="stMetricValue"] {color:#008985;}
.sei-eyebrow { font-size:11px; letter-spacing:.16em; font-weight:750; color:#4e8190; text-transform:uppercase; }
.sei-title { font-size:23px; font-weight:750; color:#09243a; margin:10px 0 5px; }
.sei-body {color:#5d7b8b;font-size:14px;line-height:1.7;}
.sei-muted {font-size:12px;color:#668697;}
.sei-brand {font-size:30px;font-weight:800;letter-spacing:-1px;color:#092e3e;}
.sei-foot {font-size:12px;color:#78919c;padding-top:10px;border-top:1px solid #dce7e9;}
</style>
""", unsafe_allow_html=True)

PAGES = ["Visão geral","Indicadores","Mercados globais","Radar de crise","Liquidez global","Previsões","Cenários",
         "Analisar investimento","Watchlist","Portfolio Builder","Assistente SEI","O meu perfil","Histórico","Fontes e metodologia"]
ICONS = ["▦","⌁","◎","◉","▤","↗","▱","⌕","☆","▣","▢","☷","◷","♢"]
if "page" not in st.session_state: st.session_state.page = "Visão geral"
if "messages" not in st.session_state: st.session_state.messages = []
if "orchestrator" not in st.session_state: st.session_state.orchestrator = SEIMacroOrchestrator()

with st.sidebar:
    st.markdown('<div class="sei-brand">〽 SEI</div><div class="sei-eyebrow">ECONOMIC INTELLIGENCE</div>', unsafe_allow_html=True)
    st.write("")
    st.markdown('<div class="sei-eyebrow">O SEU ESPAÇO DE ANÁLISE</div>',unsafe_allow_html=True)
    for i,page in enumerate(PAGES):
        if i in (7,11): st.divider()
        if st.button(f"{ICONS[i]}  {page}",key=f"nav_{i}",use_container_width=True,
                     type="primary" if st.session_state.page==page else "secondary"):
            st.session_state.page=page
            st.rerun()
    st.divider()
    st.caption("♢ Inteligência com transparência\n\nFontes identificadas. Limites claros.")

def home():
    left,right=st.columns([1.8,1],gap="medium")
    start=(date.today()-timedelta(days=365*3)).isoformat()
    end=date.today().isoformat()
    with left:
        with st.container(border=True):
            st.markdown('<div class="sei-eyebrow">EVOLUÇÃO OBSERVADA</div>',unsafe_allow_html=True)
            st.markdown('<div class="sei-title">Euro / Dólar</div>',unsafe_allow_html=True)
            alias=st.selectbox("Série a visualizar",["euribor3m","pt_inflation_ine","br_ipca","br_usd_brl","br_selic_target"],
                format_func=lambda a: next((k for k,v in DISPLAY_SERIES.items() if v==a),a),
                label_visibility="collapsed")
            n=st.segmented_control("Observações",[30,90,180],default=90,format_func=lambda x:f"{x} obs.",label_visibility="collapsed")
            try:
                payload=load_series(alias,start,end)
                df=payload["data"].dropna(subset=["value"]).sort_values("date").tail(n or 90)
                if len(df):
                    st.line_chart(df.set_index("date")["value"],height=260)
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
            st.write("")
            if st.button("Explorar fontes ↗",use_container_width=True,type="primary"):
                st.session_state.page="Fontes e metodologia"
                st.rerun()
    lowleft,lowright=st.columns([1.8,1],gap="medium")
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
                if st.button(title,use_container_width=True,key=page):
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
