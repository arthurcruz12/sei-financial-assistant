"""Multi-agent coordinator for SEI chat; agents calculate, coordinator validates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sei_agents import AgentResult


@dataclass(frozen=True)
class AgentAssignment:
    role: str
    purpose: str


AGENTS = (
    AgentAssignment("router", "Classificar intenção e ativos sem inventar parâmetros."),
    AgentAssignment("macro_data", "Consultar séries oficiais com proveniência."),
    AgentAssignment("market_data", "Obter séries de preços e verificar disponibilidade."),
    AgentAssignment("statistics", "Calcular estatísticas determinísticas."),
    AgentAssignment("econometrics", "Estimar modelos e diagnósticos."),
    AgentAssignment("technical_analysis", "Calcular indicadores e evidência histórica."),
    AgentAssignment("research", "Pesquisar factos com fontes, se houver credenciais."),
    AgentAssignment("validator", "Confirmar evidência e evitar números fabricados."),
)


class MultiAgentChat:
    """Coordinate existing specialists without changing Streamlit appearance.

    A question is classified once by the existing macro/router engines. The
    orchestrator delegates to the matching quantitative or research specialist,
    and validator checks every result before returning to the chat.
    """

    def __init__(self, orchestrator=None):
        if orchestrator is None:
            from sei_macro_runtime import SEIMacroOrchestrator
            orchestrator = SEIMacroOrchestrator()
        self.orchestrator = orchestrator

    def chat(self, message: str, *, image_bytes: Optional[bytes] = None,
             mime_type: Optional[str] = None) -> list[AgentResult]:
        if not isinstance(message, str) or not message.strip():
            return [AgentResult(agent="assistant", summary="Escreva uma pergunta económica ou financeira para começar.")]
        try:
            results = self.orchestrator.chat(message.strip(), image_bytes=image_bytes,
                                             mime_type=mime_type)
        except Exception as exc:
            return [AgentResult(agent="coordinator", summary="A análise não pôde ser concluída.",
                                warnings=[f"Erro de execução: {type(exc).__name__}"])]
        if not results:
            return [AgentResult(agent="coordinator", summary="Nenhum agente devolveu resultados verificáveis.")]
        validated = []
        for result in results:
            try:
                validated.append(self.orchestrator.validator.validate(result))
            except Exception as exc:
                validated.append(AgentResult(
                    agent="validator", summary="Um resultado foi bloqueado na validação.",
                    warnings=[f"Falha de validação: {type(exc).__name__}"]))
        return validated
