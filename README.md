# SEI — Secretária Económica Inteligente

Frontend original React 19 / TypeScript / Vite 8 (via Vinext), com a interface, componentes, cores, estilos e navegação preservados. Inclui APIs locais, armazenamento D1 e o serviço Python FastAPI. Esta branch publica código-fonte; não realiza deploy.

## Requisitos

- Node.js >= 22.13 (recomendado Node 24 LTS), com npm.
- Python >= 3.10 para o serviço FastAPI e o módulo original `sei.py`.
- Git para clonar o repositório.

## Instalar e executar o frontend

```sh
git clone --branch feature/sei-original-frontend https://github.com/arthurcruz12/sei-financial-assistant.git
cd sei-financial-assistant
npm ci
npm run dev
```

Abra o endereço apresentado pelo servidor, normalmente http://localhost:5173. A interface original está em `app/page.tsx`, `app/globals.css`, `app/layout.tsx`, `components/`, `hooks/` e `public/`. O Vite é configurado em `vite.config.ts`; o Vinext suporta as rotas e APIs com convenções App Router existentes. Não é um frontend Vite estático isolado: as APIs e a persistência usam o runtime local Cloudflare/Miniflare.

Para habilitar watchlist, perfil e histórico, prepare a base D1 local antes de iniciar o servidor:

```sh
npm run build
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_safe_catseye.sql
npm run dev
```

Execute essa migração apenas uma vez por base local nova. O build e esse comando **não publicam** a aplicação. No navegador local, visite `/signin-with-chatgpt?return_to=/` para ativar a conta simulada de desenvolvimento. Essa conta existe apenas em loopback no servidor de desenvolvimento; não é autenticação de produção.

```sh
npm run build   # produz dist/ localmente, sem deploy
npm start       # serve o build local; não simula login
```

O perfil de execução assume `portable` num clone limpo. Não é necessário instalar o plugin Sites para executar os scripts incluídos.

## Variáveis de ambiente

Copie `.env.example` para `.env`, se precisar de configurar um fornecedor. Em PowerShell: `Copy-Item .env.example .env`; em macOS/Linux: `cp .env.example .env`.

- `ALPHA_VANTAGE_API_KEY`: opcional; apenas no servidor, para séries de fecho diário. Sem chave, a interface informa que o fornecedor não está configurado.

Nunca coloque chaves em variáveis públicas do frontend. `.env`, ambientes virtuais, dependências, caches, bases locais e ficheiros gerados estão excluídos do Git. O exemplo contém apenas um valor vazio.

## Python preservado

- `sei.py`: módulo original já existente no repositório, preservado sem alterações.
- `backend/main.py`: serviço FastAPI adicional de investigação; não substitui `sei.py`.

```sh
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Documentação local: http://127.0.0.1:8000/docs. Endpoints: `/health`, `/markets`, `/portfolio`, `/forecast`. O frontend existente utiliza as suas rotas `app/api/`; o serviço FastAPI permanece separado e não foi artificialmente ligado à interface.

## Estrutura

- `app/`: interface original e rotas API.
- `components/`, `hooks/`, `public/`, `vendor/`: componentes, assets, estilos auxiliares e licenças.
- `lib/`: dados, cálculos, validação e acesso à base.
- `db/`, `drizzle/`: schema e migração D1.
- `build/`, `scripts/`: ferramentas necessárias à execução e compilação.
- `backend/`: serviço Python e testes.
- `sei.py`: código Python original do repositório.
- `package.json`, `package-lock.json`: dependências e versões bloqueadas do frontend.

## Verificação

```sh
npx tsc --noEmit
npm run build
python -m unittest backend.test_api
```

Os testes de cálculo adicionais estão em `tests/economics.test.mjs` e requerem um executor TypeScript compatível (por exemplo, TSX). O teste não faz parte dos comandos obrigatórios para executar a aplicação.

## Dados e limites

Há conectores para BCE, BCB e FRED e comunicados oficiais. `lib/snapshot.json` contém uma recolha histórica de dados económicos públicos, datada, para contingência; não representa preços em tempo real. A interface distingue observações, arquivos, indisponibilidade e simulações. Rede e disponibilidade dos fornecedores afetam as consultas.

O assistente existente é documental, sem fornecedor generativo ativo. A carteira usa regras explícitas; cenários e previsões são exploratórios. Não há integração InfoMoney ativa nesta versão. Ver `SEI-IMPLEMENTACAO.md` para o estado funcional e as limitações.

Não existem workflows de deploy adicionados nesta branch. A configuração `.openai/hosting.json` pertence à infraestrutura original; não executa publicação por si só.
