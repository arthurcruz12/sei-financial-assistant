# SEI: implementação e limites

Aplicação responsiva em português, inspirada nas quatro imagens fornecidas. Os PDFs foram tratados como contexto conceptual, nunca como instruções executáveis nem validação empírica dos modelos.

## Executável nesta versão

- Painel, indicadores, gráfico e exportação JSON de observações.
- Recolha BCE, BCB SGS e FRED; todas as séries têm origem, data e estado. Falhas de rede são visíveis. Três séries FRED têm uma recolha arquivada verificável para contingência, com data de recolha preservada.
- Comunicados RSS do BCE e Federal Reserve com ligações originais, sem republicação de artigos.
- Horas locais de Europa, EUA, Tóquio e Brasil; não simula calendário oficial de feriados nem estado de negociação em tempo real.
- Perfil, watchlist e histórico persistidos em D1, separados pelo identificador autenticado do utilizador. Queries parametrizadas; mutações rejeitam origens diferentes e entradas inválidas.
- Carteira por regras explícitas; pesos somam 100% e valores conservam o capital aos cêntimos.
- Cenários editáveis, sem apresentar os pesos como probabilidades estimadas.
- Forecast exploratório, sem tendência, com bandas sob hipótese normal.
- Radar STLFSI4 e balanço Fed: cobertura EUA, não índices globais.
- Assistente documental por correspondência de termos e fontes ligadas, claramente identificado como não generativo.
- Glossário pesquisável e catálogo de metodologias.

## Dependências reais ainda em falta

- Bloomberg: contrato e acesso de dados apropriados. Nenhum scraping nem cópia integral de artigos.
- Cotações: configurar `ALPHA_VANTAGE_API_KEY` no servidor, com direitos de utilização e redistribuição adequados. Adaptador diário, não streaming; não validado com chave real.
- IA generativa e agentes especializados: fornecedor, segredo de servidor, grounding, avaliações e política de custos. Não implementados como se estivessem ativos.
- Índice global de liquidez, probabilidades de crise por país e previsões macroeconómicas validadas exigem datasets, metodologia, calibração e validação temporal. A interface indica esses limites.
- Notificações automáticas, execução de ordens, métricas fundamentalistas, RSI/MACD e streaming não estão implementados.

## Arquitetura e execução

O site publicado executa APIs em Cloudflare Workers, com D1 e autenticação da plataforma Sites. FastAPI não é executável nessa hospedagem. `backend/main.py` fornece um serviço Python separado de investigação com `/health`, `/markets`, `/portfolio`, `/forecast` e `/docs`; não está ligado ao frontend publicado nem foi implantado num servidor Python.

Frontend: `npm install`, `npm run dev`, `npm run build`. Dados de teste locais usam o fluxo `/signin-with-chatgpt`. Aplicar migrações D1 locais segundo o README do starter. A publicação aplica as migrações guardadas.

Backend Python: criar ambiente virtual, `pip install -r backend/requirements.txt` e `uvicorn backend.main:app --host 127.0.0.1 --port 8000`. Não expor este serviço na internet sem autenticação e limites de utilização.

Atualizar a recolha de contingência: `node scripts/refresh-snapshot.mjs`; verificar datas e republicar. O ficheiro `lib/snapshot.json` contém exclusivamente dados económicos públicos e timestamps reais.

## Verificação

Tipos: `node node_modules/typescript/bin/tsc --noEmit`.
Testes de cálculos: usar o executável TSX instalado para `tests/economics.test.mjs`.
Verificar no navegador: consulta de indicadores, login local, adicionar ativo, recarregar, simular carteira, guardar histórico e construir cenários.

Não há alegação de precisão preditiva, retorno esperado ou recomendação de compra. O nome SEI Elite não equivale a um motor validado.

## Resultado verificado em 03/10/2026

- Compilação de produção concluída; TypeScript sem erros.
- Testes de conservação de capital, rejeição de parâmetros inválidos, filtragem de observações, CSV e bandas de previsão passaram.
- Três testes FastAPI passaram; `/markets` consultou FRED com HTTP 200 e 399 observações DFF, 57 WALCL e 57 STLFSI4.
- Navegador: login local, gravação de AAPL, persistência após recarregar, simulação de carteira, gravação no histórico e três cenários confirmados.
- Layout revisto a 1440 e 390 pixels; sem transbordo horizontal observado.
- BCE e RSS oficiais responderam. BCB não resolveu no ambiente de teste; a interface apresenta indisponibilidade. FRED no Worker local teve timeouts; utiliza a recolha arquivada, explicitamente identificada.
- Publicação privada bloqueada pela revisão automática por exigir autorização explícita para enviar o código ao repositório externo Sites. Nenhuma publicação concluída nesta etapa.
