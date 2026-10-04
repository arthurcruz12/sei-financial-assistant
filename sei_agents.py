from __future__ import annotations

import base64
import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yfinance as yf
from openai import OpenAI
from statsmodels.tsa.stattools import adfuller, grangercausalitytests


MIN_BACKTEST_SAMPLE = 30


@dataclass
class AgentResult:
    agent: str
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class Route:
    intent: str
    symbol: Optional[str] = None
    symbols: List[str] = field(default_factory=list)
    horizon: int = 5
    period: str = "5y"
    target_price: Optional[float] = None
    query: Optional[str] = None
    operation: Optional[str] = None
    params: Dict[str, float] = field(default_factory=dict)


class LLMClient:
    """Thin Responses API wrapper. The model is configured by OPENAI_MODEL."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    @property
    def available(self) -> bool:
        return bool(self.client and self.model)

    def route(self, message: str) -> Optional[Route]:
        if not self.available:
            return None

        instructions = """
You route requests for SEI, a quantitative economic and market assistant.
Return ONLY valid JSON with these keys:
intent: one of market_analysis,target_probability,statistics,econometrics,research,financial_math,general
symbol: string or null
symbols: array of strings
horizon: integer trading days (default 5)
period: yfinance-compatible period (default 5y)
target_price: number or null
query: string or null
operation: one of future_value,loan_payment,real_return or null
params: object of numeric parameters
Never invent a ticker when the user did not identify an asset clearly.
Examples of financial_math params:
future_value -> principal, annual_rate, years, compounds_per_year
loan_payment -> principal, annual_rate, years, payments_per_year
real_return -> nominal_return, inflation
""".strip()
        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=message,
        )
        text = response.output_text.strip()
        try:
            payload = json.loads(text)
            return Route(
                intent=str(payload.get("intent", "general")),
                symbol=payload.get("symbol"),
                symbols=[str(x).upper() for x in payload.get("symbols", []) if x],
                horizon=max(1, int(payload.get("horizon", 5))),
                period=str(payload.get("period", "5y")),
                target_price=(float(payload["target_price"]) if payload.get("target_price") is not None else None),
                query=payload.get("query"),
                operation=payload.get("operation"),
                params={k: float(v) for k, v in (payload.get("params") or {}).items() if isinstance(v, (int, float))},
            )
        except Exception:
            return None

    def research(self, query: str) -> AgentResult:
        if not self.available:
            return AgentResult(
                agent="research",
                summary="Pesquisa web indisponível: configure OPENAI_API_KEY e OPENAI_MODEL.",
                warnings=["Sem credenciais de modelo, o agente de pesquisa não pode consultar a web."],
            )
        response = self.client.responses.create(
            model=self.model,
            tools=[{"type": "web_search"}],
            instructions=(
                "Pesquise fontes primárias e confiáveis. Dê prioridade a bancos centrais, institutos estatísticos, "
                "bolsas, reguladores e documentação oficial. Diferencie fato observado de estimativa. Inclua as fontes na resposta."
            ),
            input=query,
        )
        return AgentResult(agent="research", summary=response.output_text)

    def inspect_chart_image(self, image_bytes: bytes, mime_type: str, user_text: str = "") -> AgentResult:
        if not self.available:
            return AgentResult(
                agent="vision",
                summary="Análise de imagem indisponível: configure OPENAI_API_KEY e OPENAI_MODEL.",
                warnings=["A imagem não foi usada para cálculos."],
            )
        encoded = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{encoded}"
        prompt = (
            "Identifique, se estiver visível, ticker/ativo, timeframe, níveis desenhados, indicadores, tendência e padrões. "
            "Não estime preços por pixels quando o valor não estiver legível. Retorne texto conciso e indique explicitamente o que é incerto. "
            "Esta etapa serve apenas para identificar contexto; cálculos quantitativos devem usar dados originais de mercado. "
            f"Pedido do utilizador: {user_text}"
        )
        response = self.client.responses.create(
            model=self.model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url, "detail": "high"},
                ],
            }],
        )
        return AgentResult(agent="vision", summary=response.output_text)


class MarketDataAgent:
    def history(self, symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
        if not symbol:
            raise ValueError("Ticker/ativo não informado.")
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if df.empty:
            raise ValueError(f"Nenhum dado de mercado encontrado para {symbol}.")
        if isinstance(df.columns, pd.MultiIndex):
            if symbol in df.columns.get_level_values(-1):
                df = df.xs(symbol, axis=1, level=-1)
            else:
                df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=lambda c: str(c).title()).dropna(how="all")
        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"Dados incompletos para {symbol}: faltam {sorted(missing)}")
        return df


class TechnicalAnalysisAgent:
    def __init__(self, market_data: MarketDataAgent) -> None:
        self.market_data = market_data

    @staticmethod
    def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = -delta.clip(upper=0).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        prev_close = df["Close"].shift(1)
        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out["Close"]
        out["EMA20"] = close.ewm(span=20, adjust=False).mean()
        out["EMA50"] = close.ewm(span=50, adjust=False).mean()
        out["EMA200"] = close.ewm(span=200, adjust=False).mean()
        out["RSI14"] = self._rsi(close)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        out["MACD"] = ema12 - ema26
        out["MACD_SIGNAL"] = out["MACD"].ewm(span=9, adjust=False).mean()
        out["ATR14"] = self._atr(out)
        mid = close.rolling(20).mean()
        std = close.rolling(20).std()
        out["BB_MID"] = mid
        out["BB_UPPER"] = mid + 2 * std
        out["BB_LOWER"] = mid - 2 * std
        out["REL_VOLUME"] = out["Volume"] / out["Volume"].rolling(20).mean()
        out["PRIOR_20D_HIGH"] = out["High"].shift(1).rolling(20).max()
        out["PRIOR_20D_LOW"] = out["Low"].shift(1).rolling(20).min()
        out["BREAKOUT"] = out["Close"] > out["PRIOR_20D_HIGH"]
        out["BREAKDOWN"] = out["Close"] < out["PRIOR_20D_LOW"]
        return out

    @staticmethod
    def _rsi_bucket(v: float) -> str:
        if v < 30:
            return "oversold"
        if v < 45:
            return "weak"
        if v < 55:
            return "neutral"
        if v < 70:
            return "strong"
        return "overbought"

    def analyze(self, symbol: str, horizon: int = 5, period: str = "5y", target_price: Optional[float] = None) -> AgentResult:
        raw = self.market_data.history(symbol, period=period)
        df = self.enrich(raw).dropna().copy()
        if len(df) < 250:
            raise ValueError("Histórico insuficiente para análise técnica robusta.")

        latest = df.iloc[-1]
        current_price = float(latest["Close"])
        current_regime = {
            "above_ema200": bool(latest["Close"] > latest["EMA200"]),
            "ema20_above_ema50": bool(latest["EMA20"] > latest["EMA50"]),
            "rsi_bucket": self._rsi_bucket(float(latest["RSI14"])),
            "macd_positive": bool(latest["MACD"] > latest["MACD_SIGNAL"]),
            "high_relative_volume": bool(latest["REL_VOLUME"] >= 1.2),
            "breakout": bool(latest["BREAKOUT"]),
            "breakdown": bool(latest["BREAKDOWN"]),
        }

        hist = df.iloc[:-horizon].copy()
        hist["REG_ABOVE_200"] = hist["Close"] > hist["EMA200"]
        hist["REG_EMA20_50"] = hist["EMA20"] > hist["EMA50"]
        hist["REG_RSI"] = hist["RSI14"].map(self._rsi_bucket)
        hist["REG_MACD"] = hist["MACD"] > hist["MACD_SIGNAL"]
        hist["REG_VOL"] = hist["REL_VOLUME"] >= 1.2
        hist["FWD_CLOSE"] = df["Close"].shift(-horizon).reindex(hist.index)
        hist["FWD_RETURN"] = hist["FWD_CLOSE"] / hist["Close"] - 1
        future_high = pd.concat([df["High"].shift(-i) for i in range(1, horizon + 1)], axis=1).max(axis=1)
        future_low = pd.concat([df["Low"].shift(-i) for i in range(1, horizon + 1)], axis=1).min(axis=1)
        hist["FWD_MAX"] = future_high.reindex(hist.index)
        hist["FWD_MIN"] = future_low.reindex(hist.index)

        mask = (
            (hist["REG_ABOVE_200"] == current_regime["above_ema200"])
            & (hist["REG_EMA20_50"] == current_regime["ema20_above_ema50"])
            & (hist["REG_RSI"] == current_regime["rsi_bucket"])
            & (hist["REG_MACD"] == current_regime["macd_positive"])
        )
        if current_regime["high_relative_volume"]:
            mask &= hist["REG_VOL"]
        matched = hist.loc[mask].dropna(subset=["FWD_RETURN", "FWD_MAX", "FWD_MIN"])

        sample_size = int(len(matched))
        probability_up = None
        target_probability = None
        avg_return = None
        median_return = None
        confidence = "insuficiente"
        if sample_size >= MIN_BACKTEST_SAMPLE:
            probability_up = float((matched["FWD_RETURN"] > 0).mean())
            avg_return = float(matched["FWD_RETURN"].mean())
            median_return = float(matched["FWD_RETURN"].median())
            confidence = "alta" if sample_size >= 200 else "média" if sample_size >= 75 else "baixa"
            if target_price is not None and target_price > 0:
                target_probability = float((matched["FWD_MAX"] >= target_price).mean())

        support = float(latest["PRIOR_20D_LOW"])
        resistance = float(latest["PRIOR_20D_HIGH"])
        atr = float(latest["ATR14"])
        stop = current_price - 1.5 * atr
        target_atr = current_price + 2.0 * atr
        rr = (target_atr - current_price) / max(current_price - stop, 1e-9)

        if current_regime["above_ema200"] and current_regime["ema20_above_ema50"] and current_regime["macd_positive"]:
            bias = "altista"
        elif (not current_regime["above_ema200"]) and (not current_regime["ema20_above_ema50"]) and (not current_regime["macd_positive"]):
            bias = "baixista"
        else:
            bias = "misto/lateral"

        summary = (
            f"{symbol.upper()} | preço {current_price:.2f} | viés {bias} | RSI {float(latest['RSI14']):.1f} | "
            f"suporte {support:.2f} | resistência {resistance:.2f}."
        )
        warnings: List[str] = []
        if sample_size < MIN_BACKTEST_SAMPLE:
            warnings.append(
                f"Apenas {sample_size} ocorrências históricas comparáveis; não foi publicada uma probabilidade para evitar falsa precisão."
            )

        data = {
            "symbol": symbol.upper(),
            "last_date": str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1]),
            "current_price": round(current_price, 4),
            "bias": bias,
            "indicators": {
                "ema20": round(float(latest["EMA20"]), 4),
                "ema50": round(float(latest["EMA50"]), 4),
                "ema200": round(float(latest["EMA200"]), 4),
                "rsi14": round(float(latest["RSI14"]), 2),
                "macd": round(float(latest["MACD"]), 4),
                "macd_signal": round(float(latest["MACD_SIGNAL"]), 4),
                "atr14": round(atr, 4),
                "relative_volume": round(float(latest["REL_VOLUME"]), 2),
            },
            "levels": {
                "support_20d": round(support, 4),
                "resistance_20d": round(resistance, 4),
                "atr_stop_reference": round(stop, 4),
                "atr_target_reference": round(target_atr, 4),
                "risk_reward_reference": round(rr, 2),
            },
            "regime": current_regime,
            "backtest": {
                "horizon_trading_days": horizon,
                "sample_size": sample_size,
                "probability_positive_close": (round(probability_up * 100, 2) if probability_up is not None else None),
                "average_return_percent": (round(avg_return * 100, 3) if avg_return is not None else None),
                "median_return_percent": (round(median_return * 100, 3) if median_return is not None else None),
                "target_price": target_price,
                "probability_reach_target_percent": (round(target_probability * 100, 2) if target_probability is not None else None),
                "confidence": confidence,
                "method": "Frequência histórica de regimes técnicos comparáveis; não é probabilidade causal nem garantia futura.",
            },
        }
        return AgentResult(
            agent="technical_analysis",
            summary=summary,
            data=data,
            sources=[f"Yahoo Finance via yfinance ({symbol.upper()})"],
            warnings=warnings,
        )


class StatisticsAgent:
    def __init__(self, market_data: MarketDataAgent) -> None:
        self.market_data = market_data

    def analyze(self, symbol: str, period: str = "5y") -> AgentResult:
        df = self.market_data.history(symbol, period=period)
        returns = df["Close"].pct_change().dropna()
        n = len(returns)
        mean = returns.mean()
        std = returns.std(ddof=1)
        annual_return = (1 + mean) ** 252 - 1
        annual_vol = std * math.sqrt(252)
        sem = std / math.sqrt(n)
        ci_low = mean - 1.96 * sem
        ci_high = mean + 1.96 * sem
        downside = returns[returns < 0]
        downside_std = downside.std(ddof=1) * math.sqrt(252) if len(downside) > 1 else np.nan
        sharpe = annual_return / annual_vol if annual_vol > 0 else np.nan
        sortino = annual_return / downside_std if downside_std and not np.isnan(downside_std) else np.nan
        wealth = (1 + returns).cumprod()
        drawdown = wealth / wealth.cummax() - 1

        data = {
            "symbol": symbol.upper(),
            "observations": n,
            "daily_mean_return_percent": round(float(mean * 100), 4),
            "daily_median_return_percent": round(float(returns.median() * 100), 4),
            "annualized_return_percent": round(float(annual_return * 100), 2),
            "annualized_volatility_percent": round(float(annual_vol * 100), 2),
            "max_drawdown_percent": round(float(drawdown.min() * 100), 2),
            "sharpe_zero_rf": round(float(sharpe), 3) if not np.isnan(sharpe) else None,
            "sortino_zero_rf": round(float(sortino), 3) if not np.isnan(sortino) else None,
            "daily_mean_95ci_percent": [round(float(ci_low * 100), 4), round(float(ci_high * 100), 4)],
            "positive_days_percent": round(float((returns > 0).mean() * 100), 2),
        }
        return AgentResult(
            agent="statistics",
            summary=f"Estatística de {symbol.upper()} calculada com {n} retornos diários reais.",
            data=data,
            sources=[f"Yahoo Finance via yfinance ({symbol.upper()})"],
        )


class EconometricsAgent:
    def __init__(self, market_data: MarketDataAgent) -> None:
        self.market_data = market_data

    def analyze(self, symbols: List[str], period: str = "5y") -> AgentResult:
        if len(symbols) < 2:
            raise ValueError("Econometria requer pelo menos dois ativos/séries nesta versão.")
        series: Dict[str, pd.Series] = {}
        for symbol in symbols[:4]:
            df = self.market_data.history(symbol, period=period)
            series[symbol.upper()] = df["Close"].pct_change().rename(symbol.upper())
        panel = pd.concat(series.values(), axis=1).dropna()
        y_name = symbols[0].upper()
        x_names = [s.upper() for s in symbols[1:4]]
        y = panel[y_name]
        X = sm.add_constant(panel[x_names])
        model = sm.OLS(y, X).fit(cov_type="HC3")
        adf = adfuller(y.dropna(), autolag="AIC")

        coefficients = {}
        for name in model.params.index:
            coefficients[name] = {
                "coef": round(float(model.params[name]), 6),
                "p_value": round(float(model.pvalues[name]), 6),
                "std_error_hc3": round(float(model.bse[name]), 6),
            }

        granger = {}
        if len(x_names) == 1 and len(panel) > 80:
            pair = panel[[y_name, x_names[0]]].dropna()
            try:
                results = grangercausalitytests(pair, maxlag=5, verbose=False)
                granger = {
                    str(lag): round(float(result[0]["ssr_ftest"][1]), 6)
                    for lag, result in results.items()
                }
            except Exception:
                granger = {}

        data = {
            "dependent": y_name,
            "explanatory": x_names,
            "observations": int(model.nobs),
            "r_squared": round(float(model.rsquared), 4),
            "adjusted_r_squared": round(float(model.rsquared_adj), 4),
            "coefficients": coefficients,
            "adf_dependent_returns": {
                "statistic": round(float(adf[0]), 4),
                "p_value": round(float(adf[1]), 6),
            },
            "granger_p_values_by_lag": granger,
            "method_notes": [
                "OLS sobre retornos diários com erros-padrão robustos HC3.",
                "Coeficientes descrevem associação condicional; não provam causalidade.",
                "O teste de Granger, quando calculado, avalia precedência preditiva e também não prova causalidade estrutural.",
            ],
        }
        return AgentResult(
            agent="econometrics",
            summary=f"OLS estimado: {y_name} em função de {', '.join(x_names)}.",
            data=data,
            sources=[f"Yahoo Finance via yfinance ({', '.join([s.upper() for s in symbols[:4]])})"],
        )


class FinancialMathAgent:
    def run(self, operation: str, params: Dict[str, float]) -> AgentResult:
        if operation == "future_value":
            p = params["principal"]
            r = params["annual_rate"] / 100
            years = params["years"]
            n = params.get("compounds_per_year", 12)
            value = p * (1 + r / n) ** (n * years)
            data = {"future_value": round(value, 2)}
        elif operation == "loan_payment":
            p = params["principal"]
            annual_rate = params["annual_rate"] / 100
            years = params["years"]
            n = params.get("payments_per_year", 12)
            rate = annual_rate / n
            payments = n * years
            if rate == 0:
                payment = p / payments
            else:
                payment = p * rate / (1 - (1 + rate) ** (-payments))
            data = {"payment": round(payment, 2), "number_of_payments": int(payments)}
        elif operation == "real_return":
            nominal = params["nominal_return"] / 100
            inflation = params["inflation"] / 100
            real = (1 + nominal) / (1 + inflation) - 1
            data = {"real_return_percent": round(real * 100, 4)}
        else:
            raise ValueError(f"Operação matemática não suportada: {operation}")
        return AgentResult(agent="financial_math", summary="Cálculo concluído por fórmula determinística.", data=data)


class ValidatorAgent:
    """Checks evidence and suppresses unsupported market probabilities."""

    def validate(self, result: AgentResult) -> AgentResult:
        if result.agent == "technical_analysis":
            bt = result.data.get("backtest", {})
            n = int(bt.get("sample_size") or 0)
            if n < MIN_BACKTEST_SAMPLE:
                bt["probability_positive_close"] = None
                bt["probability_reach_target_percent"] = None
                result.data["backtest"] = bt
            for key in ("probability_positive_close", "probability_reach_target_percent"):
                value = bt.get(key)
                if value is not None and not (0 <= float(value) <= 100):
                    raise ValueError(f"Probabilidade inválida produzida pelo motor: {value}")
        return result


class RouterAgent:
    TICKER_RE = re.compile(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b")

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def route(self, message: str) -> Route:
        llm_route = self.llm.route(message)
        if llm_route:
            if llm_route.symbol:
                llm_route.symbol = llm_route.symbol.upper()
            return llm_route

        lower = message.lower()
        tickers = self.TICKER_RE.findall(message.upper())
        symbol = tickers[0] if tickers else None
        horizon_match = re.search(r"(\d+)\s*(?:dias?|preg[oõ]es?)", lower)
        horizon = int(horizon_match.group(1)) if horizon_match else 5
        target_match = re.search(r"(?:alvo|chegar|bater|atingir)\s*(?:a|em|nos?)?\s*[$€£]?\s*(\d+(?:[.,]\d+)?)", lower)
        target = float(target_match.group(1).replace(",", ".")) if target_match else None

        if any(k in lower for k in ["regress", "econometr", "granger", "cointegra", "ols"]):
            return Route(intent="econometrics", symbols=tickers, horizon=horizon)
        if any(k in lower for k in ["desvio", "volatil", "drawdown", "sharpe", "estatíst", "estatist"]):
            return Route(intent="statistics", symbol=symbol, horizon=horizon)
        if any(k in lower for k in ["chance", "probabilidade", "bater", "atingir", "alvo"]):
            return Route(intent="target_probability", symbol=symbol, horizon=horizon, target_price=target)
        if any(k in lower for k in ["rsi", "macd", "suporte", "resist", "breakout", "romp", "gráfico", "grafico", "técnica", "tecnica"]):
            return Route(intent="market_analysis", symbol=symbol, horizon=horizon)
        if any(k in lower for k in ["notícia", "noticia", "hoje", "atual", "pesquise", "procure", "bce", "fed", "inflação", "inflacao"]):
            return Route(intent="research", query=message)
        return Route(intent="general", query=message)


class SEIOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.market = MarketDataAgent()
        self.technical = TechnicalAnalysisAgent(self.market)
        self.statistics = StatisticsAgent(self.market)
        self.econometrics = EconometricsAgent(self.market)
        self.math = FinancialMathAgent()
        self.validator = ValidatorAgent()
        self.router = RouterAgent(self.llm)

    def chat(self, message: str, image_bytes: Optional[bytes] = None, mime_type: Optional[str] = None) -> List[AgentResult]:
        results: List[AgentResult] = []
        if image_bytes:
            vision = self.llm.inspect_chart_image(image_bytes, mime_type or "image/png", message)
            results.append(vision)
            visual_tickers = RouterAgent.TICKER_RE.findall(vision.summary.upper())
        else:
            visual_tickers = []

        route = self.router.route(message)
        if not route.symbol and visual_tickers:
            route.symbol = visual_tickers[0]

        try:
            if route.intent in {"market_analysis", "target_probability"}:
                if not route.symbol:
                    raise ValueError("Informe o ticker/ativo para eu buscar os dados reais (ex.: AAPL, NVDA, PETR4.SA).")
                result = self.technical.analyze(
                    route.symbol,
                    horizon=route.horizon,
                    period=route.period,
                    target_price=route.target_price,
                )
                results.append(self.validator.validate(result))
            elif route.intent == "statistics":
                if not route.symbol:
                    raise ValueError("Informe o ticker/ativo para a análise estatística.")
                results.append(self.statistics.analyze(route.symbol, period=route.period))
            elif route.intent == "econometrics":
                symbols = route.symbols or ([route.symbol] if route.symbol else [])
                if len(symbols) < 2:
                    raise ValueError("Informe pelo menos duas séries/tickers para a regressão, por exemplo: AAPL SPY.")
                results.append(self.econometrics.analyze(symbols, period=route.period))
            elif route.intent == "financial_math":
                if not route.operation:
                    raise ValueError("Não consegui identificar a operação matemática.")
                results.append(self.math.run(route.operation, route.params))
            elif route.intent == "research":
                results.append(self.llm.research(route.query or message))
            else:
                if self.llm.available:
                    results.append(self.llm.research(message))
                else:
                    results.append(AgentResult(
                        agent="general",
                        summary=(
                            "Consigo executar análise técnica, estatística e econométrica sem LLM quando há ticker. "
                            "Para perguntas gerais e pesquisa atual, configure OPENAI_API_KEY e OPENAI_MODEL."
                        ),
                    ))
        except Exception as exc:
            results.append(AgentResult(agent="orchestrator", summary=f"Não consegui concluir esta etapa: {exc}", warnings=[str(exc)]))
        return results


def result_to_markdown(result: AgentResult) -> str:
    parts = [f"### {result.agent.replace('_', ' ').title()}", result.summary]
    if result.data:
        parts.append("```json\n" + json.dumps(result.data, ensure_ascii=False, indent=2) + "\n```")
    if result.sources:
        parts.append("**Fontes:** " + "; ".join(result.sources))
    if result.warnings:
        parts.append("**Avisos:** " + " | ".join(result.warnings))
    return "\n\n".join(parts)
