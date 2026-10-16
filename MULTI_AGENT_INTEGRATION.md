# Integração do site original com os agentes Python

O frontend original mantém todo o seu CSS, componentes e navegação. A única alteração funcional no chat é chamar POST /api/assistant, que funciona como proxy seguro para um serviço FastAPI independente.

## Serviço Python multiagente

O código do serviço está na branch feature/real-data-econometrics, em sei_api.py, e usa o coordenador sei_multi_agent.py e os agentes já existentes.

Instalar na máquina que aloja a API:

    pip install -r requirements.txt

Configurar variáveis privadas no serviço (não as incluir no Git):

    SEI_BRIDGE_TOKEN=<token-aleatorio-longo>
    OPENAI_API_KEY=<opcional>
    OPENAI_MODEL=<opcional>

Iniciar:

    uvicorn sei_api:app --host 0.0.0.0 --port 8000

Verificar GET /health. Publicar num serviço que execute Python e disponibilize URL HTTPS; o Streamlit Community Cloud não é utilizado como gateway FastAPI.

## Frontend original

No ambiente do frontend, configurar (variáveis server-only):

    SEI_AGENT_API_URL=https://URL-HTTPS-DA-API
    SEI_BRIDGE_TOKEN=<mesmo-token-da-API>

Executar com os comandos originais do README. As credenciais são usadas apenas no servidor na rota app/api/assistant/route.ts e não são enviadas ao navegador.

A rota devolve uma mensagem explícita quando a API não está configurada; não inventa dados. A API e o frontend ainda precisam de deploy e testes end-to-end antes de considerar a integração ativa na Internet.

O Streamlit na branch feature/real-data-econometrics permanece separado e sem alteração de aparência.
