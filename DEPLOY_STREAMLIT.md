# Deploy gratuito — SEI no Streamlit Community Cloud

A aplicação utiliza Streamlit e Python. Não publicar chaves de API no GitHub.

1. Aceda a https://share.streamlit.io/ e inicie sessão com o GitHub.
2. Escolha **Create app** → **Yup, I have an app**.
3. Preencha:
   - Repository: `arthurcruz12/sei-financial-assistant`
   - Branch: `feature/real-data-econometrics`
   - Main file path: `streamlit_app.py`
4. Nas definições avançadas, use Python 3.12 (ou versão compatível) e adicione os segredos opcionais:
   ```toml
   OPENAI_API_KEY = "substitua-pela-sua-chave"
   OPENAI_MODEL = "modelo-disponivel-na-sua-conta"
   FRED_API_KEY = "chave-opcional-para-FRED"
   ```
   **Nunca coloque valores reais num commit.** A aplicação pode consultar ECB/Eurostat/INE/BCB sem chaves.
5. Clique em **Deploy** e verifique os logs. O alojamento será gratuito sujeito às condições e limites do Community Cloud.

## Validação após publicar

- Abra o painel quantitativo.
- Consulte IPCA Brasil e Euribor com um intervalo válido; confirme fonte, valor e histórico.
- Execute regressão com pelo menos 30 observações comuns e variáveis independentes não colineares.
- Se aparecer erro, consulte **Manage app → Logs** e corrija a dependência/API indicada.
- Não faça merge na main antes de testar UI, respostas de API e dados.

## Nota sobre arquitetura

O Community Cloud aloja uma app Streamlit (interface e computação Python no mesmo processo).
Se o objetivo for uma API backend REST separada para frontend React/Next.js, isso requer um serviço distinto (por exemplo, FastAPI) e alojamento adequado.
