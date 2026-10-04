# 🧠 SEI — Smart Economic Intelligence

SEI is a conversational quantitative assistant for economics, markets, mathematics, statistics and econometrics.

> **AI interprets and researches. Deterministic Python code calculates.**

The chat must not invent prices, indicators, probabilities or econometric results.

## Multi-agent architecture

The user talks to one SEI chat. Internally, specialist agents handle the work:

- **Router Agent** — natural PT/EN financial language and intent routing.
- **Research Agent** — current web research with primary-source preference.
- **Vision Agent** — reads chart screenshots for visible context, never as a substitute for raw prices.
- **Market Data Agent** — real OHLCV through `yfinance`.
- **Technical Analysis Agent** — EMA 20/50/200, RSI, MACD, ATR, Bollinger, relative volume, support/resistance, breakout regimes and historical matching.
- **Statistics Agent** — returns, volatility, confidence intervals, drawdown, Sharpe and Sortino.
- **Econometrics Agent** — OLS/HC3, ADF and Granger for market series.
- **Official Macro Data Agent** — ECB/BCE, Eurostat, INE Portugal, FRED and OECD.
- **Macro Econometrics Agent** — aligns market and official macro series in a common frequency and estimates OLS/HC3, correlations, ADF and Granger when appropriate.
- **Financial Math Agent** — deterministic financial formulas.
- **Validator Agent** — suppresses unsupported quantitative claims.

## Official macroeconomic data

`macro_data.py` provides direct connectors without webpage scraping:

- **ECB Data Portal API (SDMX)** — Euribor 3M/6M/12M and the ECB deposit facility rate presets, plus generic ECB flow/key access.
- **Eurostat Statistics API (JSON-stat)** — the chat uses the current `prc_hicp_minr` HICP structure for Portugal inflation (`coicop18=TOTAL`), plus unemployment/GDP datasets and generic dataset/filter access.
- **INE Portugal JSON indicator API** — Portugal CPI inflation, real-GDP growth and unemployment presets, plus generic indicator/dimension access.
- **FRED API** — CPI, unemployment, real GDP and Fed Funds presets. `FRED_API_KEY` is required by FRED.
- **OECD Data Explorer SDMX API** — generic flow/key access and a Portugal unemployment preset used by the chat.

Every `OfficialSeries` carries source, series ID, frequency, unit, exact request URL and metadata so the result can expose provenance.

## Market + macro econometrics

The SEI can now receive a question such as:

```text
Cruza SPY com inflação e Euribor nos últimos 10 anos.
```

The engine retrieves market and official macro data, converts market prices to period returns, aligns series to the coarsest relevant frequency, estimates OLS with HC3 robust standard errors, returns coefficients/p-values/R²/correlations, runs ADF, and can run Granger predictive-precedence tests for suitable two-series cases.

A macro/market regression is **not automatically a causal model**. Ordinary reference-period data also do not preserve the exact historical publication timestamp or vintage. The SEI therefore warns that these results must not be interpreted as a look-ahead-free trading backtest unless vintage/release-date handling is added.

## Probability policy

SEI does **not** let the LLM invent statements such as “72% chance of rising”. Technical-market probabilities come from historically comparable regimes and are suppressed below 30 comparable observations.

For a target-price question, SEI converts today's target into the percentage return required and tests that same relative move on historical comparable regimes instead of comparing nominal prices across eras.

## Vocabulary

The fallback understands broad Portuguese/English vocabulary across technical analysis, statistics, econometrics and macroeconomics, including support/resistance, breakout, pullback, overbought/oversold, drawdown, Sharpe, Sortino, OLS, ADF, Granger, cointegration, ARIMA, VAR, GARCH, inflation, GDP/PIB, unemployment, Euribor, policy rates and yields.

## Chart screenshots

A chart image can be uploaded in the Streamlit interface. Vision extracts visible asset/timeframe/pattern context; whenever an asset is identified, quantitative calculations use original market data rather than pixel measurements.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables as needed:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
export FRED_API_KEY="..."   # only required for FRED
```

Then:

```bash
streamlit run streamlit_app.py
```

## Example questions

```text
Analisa NVDA em 10 pregões.
Qual a chance de AAPL atingir 300 em 20 dias?
Calcula volatilidade, Sharpe e drawdown de SPY.
Regressão AAPL SPY.
Mostre inflação, PIB, desemprego e Euribor em Portugal.
Cruza SPY com inflação e Euribor nos últimos 10 anos.
Regressão NVDA com Euribor e taxa do BCE.
Use Eurostat para comparar desemprego e PIB.
OECD desemprego de Portugal.
FRED fed funds e desemprego dos EUA.
Pesquise a decisão mais recente do BCE.
```

## Tests

The GitHub workflow runs deterministic unit/parser/econometrics tests plus live smoke tests against the public ECB, Eurostat, INE and OECD APIs. An INE connection timeout from a CI runner is treated as an external availability skip, while malformed responses still fail. FRED smoke testing runs when `FRED_API_KEY` is configured.

The live smoke suite is used to catch upstream schema/API changes before merge; the 2026 Eurostat HICP migration was caught this way and the connector was updated to the current `prc_hicp_minr`/ECOICOP-2018 structure.

## Current scope

The official macro connectors and market/macro econometrics are now part of this branch. High-value next steps are vintage/release-calendar support for true point-in-time backtests, richer cointegration/VAR/VECM diagnostics, transaction-cost-aware strategy evaluation and a cleaner human-readable result renderer.
