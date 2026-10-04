from __future__ import annotations

import mimetypes

import streamlit as st

from sei_agents import result_to_markdown
from sei_macro_runtime import SEIMacroOrchestrator


st.set_page_config(page_title="SEI", page_icon="🧠", layout="wide")
st.title("SEI — Inteligência Económica Quantitativa")
st.caption("Um único chat; agentes de mercado, matemática, estatística, econometria e dados macro oficiais trabalham por trás da resposta.")

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = SEIMacroOrchestrator()
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Gráfico / screenshot")
    uploaded = st.file_uploader("Opcional: envie um gráfico", type=["png", "jpg", "jpeg", "webp"])
    st.caption(
        "O agente visual identifica ticker, timeframe e padrões. Os cálculos usam dados originais de mercado, "
        "não medições aproximadas dos pixels."
    )
    st.divider()
    st.markdown(
        "**Perguntas que o SEI já entende**\n\n"
        "- `Analisa NVDA em 10 pregões`\n"
        "- `Qual a chance de AAPL atingir 300 em 20 dias?`\n"
        "- `Volatilidade, Sharpe e drawdown de SPY`\n"
        "- `Regressão AAPL SPY`\n"
        "- `Mostre inflação, PIB, desemprego e Euribor em Portugal`\n"
        "- `Cruza SPY com inflação e Euribor nos últimos 10 anos`\n"
        "- `Regressão NVDA com Euribor e taxa do BCE`\n"
        "- `Use Eurostat para comparar desemprego e PIB`\n"
        "- `OECD desemprego de Portugal`\n"
        "- `FRED fed funds e desemprego dos EUA`\n"
        "- `Pesquise a decisão mais recente do BCE`"
    )
    st.divider()
    st.caption(
        "Fontes macro: BCE/ECB, Eurostat, INE Portugal, FRED e OECD. "
        "FRED requer FRED_API_KEY."
    )
    st.caption(
        "Percentagens só são mostradas quando existe amostra quantitativa suficiente. "
        "Sinais são apoio analítico, não ordens de compra ou venda."
    )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Pergunte ao SEI...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    image_bytes = uploaded.getvalue() if uploaded is not None else None
    mime_type = mimetypes.guess_type(uploaded.name)[0] if uploaded is not None else None

    with st.chat_message("assistant"):
        with st.spinner("Os agentes estão buscando dados oficiais e executando a análise..."):
            results = st.session_state.orchestrator.chat(
                prompt,
                image_bytes=image_bytes,
                mime_type=mime_type,
            )
        answer = "\n\n---\n\n".join(result_to_markdown(r) for r in results)
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
