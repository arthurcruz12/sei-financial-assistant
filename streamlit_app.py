from __future__ import annotations

import mimetypes

import streamlit as st

from sei_agents import SEIOrchestrator, result_to_markdown


st.set_page_config(page_title="SEI", page_icon="🧠", layout="wide")
st.title("SEI — Inteligência Económica Quantitativa")
st.caption("Chat com agentes especializados em pesquisa, mercado, matemática, estatística e econometria.")

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = SEIOrchestrator()
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Análise de gráfico")
    uploaded = st.file_uploader("Opcional: envie screenshot do gráfico", type=["png", "jpg", "jpeg", "webp"])
    st.caption("A imagem identifica contexto; preços e probabilidades são calculados com dados originais, quando o ticker é identificado.")
    st.divider()
    st.markdown(
        "**Exemplos**\n\n"
        "- `Analisa NVDA em 10 pregões`\n"
        "- `Chance de AAPL atingir 300 em 20 dias`\n"
        "- `Volatilidade e drawdown de SPY`\n"
        "- `Regressão AAPL SPY`\n"
        "- `Pesquise a decisão mais recente do BCE`"
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
        with st.spinner("Analisando..."):
            results = st.session_state.orchestrator.chat(prompt, image_bytes=image_bytes, mime_type=mime_type)
        answer = "\n\n---\n\n".join(result_to_markdown(r) for r in results)
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
