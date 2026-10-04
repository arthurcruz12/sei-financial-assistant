# 🧠 SEI — Smart Economic Intelligence

SEI is a conversational quantitative assistant for economics, markets, mathematics, statistics and econometrics.

The core rule is simple:

> **AI interprets and researches. Deterministic Python code calculates.**

The chat must not invent prices, indicators, probabilities or econometric results.

## Multi-agent architecture

The user talks to one SEI chat. Internally, an orchestrator routes the request to specialist agents:

- **Router Agent** — understands natural Portuguese/English financial language and selects the correct specialist.
- **Research Agent** — uses the OpenAI Responses API web-search tool for current public information and primary sources.
- **Vision Agent** — reads chart screenshots to identify visible ticker/timeframe/pattern context; it does not use pixels as a substitute for market data.
- **Market Data Agent** — retrieves real OHLCV market data using `yfinance`.
- **Technical Analysis Agent** — EMA 20/50/200, RSI, MACD, ATR, Bollinger Bands, relative volume, support/resistance, breakouts and regime matching.
- **Statistics Agent** — returns, volatility, confidence intervals, drawdown, Sharpe, Sortino and positive-day frequency.
- **Econometrics Agent** — OLS with HC3 robust errors, ADF and Granger predictive-precedence tests.
- **Financial Math Agent** — deterministic compound-interest, loan-payment and real-return calculations.
- **Validator Agent** — suppresses unsupported market probabilities and checks quantitative outputs.

## Probability policy

SEI does **not** let the LLM invent statements such as “72% chance of rising”.

For technical-market probabilities the engine:

1. identifies the current technical regime;
2. finds historically comparable observations;
3. evaluates forward returns over the requested horizon;
4. reports sample size and confidence;
5. suppresses probabilities when there are fewer than 30 comparable cases.

For a question such as:

> `Qual a chance de AAPL atingir 300 em 20 pregões?`

SEI converts the target into the **percentage return required from today's price**, then tests whether historical comparable regimes achieved at least that return within the same horizon. It does not compare today's nominal target against old nominal share prices.

## Vocabulary

The deterministic fallback understands a broad PT/EN vocabulary including concepts such as:

- support/resistance, suporte/resistência;
- breakout, breakdown, pullback, retest;
- overbought/sobrecomprado, oversold/sobrevendido;
- momentum, divergence, volume, VWAP, RSI, MACD, EMA, ATR, ADX;
- volatility, drawdown, Sharpe, Sortino, confidence interval;
- OLS, Logit/Probit vocabulary, heteroskedasticity, autocorrelation, ADF, cointegration, Granger, ARIMA, VAR, VECM and GARCH;
- inflation, GDP, Euribor, central-bank rates, yields and other macroeconomic terminology.

With an OpenAI model configured, the Router Agent handles much broader natural-language paraphrases as well.

## Chart screenshots

A chart image can be uploaded in the Streamlit interface.

The Vision Agent extracts only visible context such as asset, timeframe, indicators and patterns. Whenever an asset can be identified, quantitative calculations are performed from original market data instead of measurements inferred from screenshot pixels.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
```

Then run:

```bash
streamlit run streamlit_app.py
```

## Example questions

```text
Analisa NVDA em 10 pregões.
Qual a chance de AAPL atingir 300 em 20 dias?
NVDA está esticada ou sobrecomprada?
Calcula volatilidade, Sharpe e drawdown de SPY.
Faz uma regressão de AAPL contra SPY.
Pesquise a decisão mais recente do BCE e explique o impacto provável sobre a Euribor.
```

## Current scope

This branch is a functional quantitative foundation, not a finished trading system. The next high-value additions are official macroeconomic data connectors (ECB, Eurostat, INE, FRED/OECD), stronger walk-forward/out-of-sample validation, transaction-cost-aware backtests, richer econometric diagnostics and a cleaner human-readable result renderer.
