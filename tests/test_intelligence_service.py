"""
tests/test_intelligence_service.py

Teste do último invariante de segurança da Fase B: em
IntelligenceService.decide_action(), a IA pode escolher SE e QUAL
ferramenta chamar, mas nunca ONDE - qualquer alvo que a IA proponha
no tool_call é sempre substituído por mission_target antes do
dispatch (hermes/core/intelligence_service.py).

Usa um "cérebro" falso (FakeIntelligence) em vez do Ollama real, para
controlar exatamente o tool_call que "a IA" propõe, e substitui
tool_dispatcher.dispatch por uma versão que só regista o alvo
recebido, sem executar nada de verdade.
"""
from hermes.core import intelligence_service as isvc
from hermes.core import tool_dispatcher


class FakeIntelligence:
    """Simula HermesIntelligence: gerar_com_tools() devolve sempre os
    tool_calls indicados na construção, sem chamar o Ollama real."""

    def __init__(self, tool_calls):
        self._tool_calls = tool_calls

    def gerar(self, prompt):
        return "resposta nao usada neste teste"

    def gerar_com_tools(self, prompt, tools):
        return {"tool_calls": self._tool_calls, "content": ""}


def _service_com_alvo_proposto(monkeypatch, alvo_proposto_pela_ia):
    """Prepara um IntelligenceService com uma IA falsa que tenta
    propor `alvo_proposto_pela_ia`, e um dispatch falso que só
    regista o alvo que realmente recebeu."""
    tool_call_da_ia = {
        "function": {"name": "run_nmap", "arguments": {"target": alvo_proposto_pela_ia}}
    }
    fake_intelligence = FakeIntelligence(tool_calls=[tool_call_da_ia])

    monkeypatch.setattr(isvc, "build_context", lambda *a, **k: "contexto-fake")

    alvos_recebidos = []

    def fake_dispatch(tool_call):
        alvo = tool_call["function"]["arguments"]["target"]
        alvos_recebidos.append(alvo)
        return {"ok": True, "ferramenta": "nmap", "target": alvo, "eventos": {}}

    monkeypatch.setattr(tool_dispatcher, "dispatch", fake_dispatch)
    monkeypatch.setattr(tool_dispatcher, "construir_schemas_tools", lambda: [])

    return isvc.IntelligenceService(fake_intelligence), alvos_recebidos


def test_mission_target_sobrepoe_se_a_alvo_inventado_pela_ia(monkeypatch):
    # A IA tenta impor 8.8.8.8 - o mission_target (aqui o default,
    # 127.0.0.1) tem sempre de prevalecer antes do dispatch.
    service, alvos_recebidos = _service_com_alvo_proposto(monkeypatch, "8.8.8.8")

    resultado = service.decide_action("ha algo suspeito?")

    assert alvos_recebidos == ["127.0.0.1"]
    assert resultado["acoes"][0]["tool_call"]["function"]["arguments"]["target"] == "127.0.0.1"


def test_mission_target_explicito_tambem_sobrepoe_se_a_ia(monkeypatch):
    # Confirma que não é só o default a funcionar - um mission_target
    # explícito e diferente também vence, para o cenário real do user
    # (ex: "verificar o IP do meu amigo 192.168.x.x").
    service, alvos_recebidos = _service_com_alvo_proposto(monkeypatch, "10.0.0.99")

    resultado = service.decide_action(
        "ha algo suspeito?", mission_target="192.168.100.5"
    )

    assert alvos_recebidos == ["192.168.100.5"]
    assert resultado["acoes"][0]["tool_call"]["function"]["arguments"]["target"] == "192.168.100.5"
