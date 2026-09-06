"""
tests/test_tool_dispatcher.py

Testes do portão entre a decisão da IA (tool_calls) e a execução
real das ferramentas (hermes/core/tool_dispatcher.py).

NOTA: o override de mission_target (o alvo definido pelo utilizador
sobrepor-se sempre a qualquer alvo que a IA proponha) não vive aqui -
vive em IntelligenceService.decide_action(), que chama dispatch()
já com o alvo corrigido. Esse caso fica para test_intelligence_service.py
(ou equivalente), a escrever depois de ver esse ficheiro.
"""
from hermes.core import tool_dispatcher


def _tool_call(nome_funcao, target=None):
    argumentos = {} if target is None else {"target": target}
    return {"function": {"name": nome_funcao, "arguments": argumentos}}


def test_funcao_fora_da_allowlist_e_rejeitada():
    resultado = tool_dispatcher.dispatch(_tool_call("run_rm_rf", "127.0.0.1"))
    assert resultado["ok"] is False
    assert "nao esta na lista pre-aprovada" in resultado["erro"]


def test_alvo_em_falta_e_rejeitado():
    resultado = tool_dispatcher.dispatch(_tool_call("run_nmap"))
    assert resultado["ok"] is False
    assert "Alvo em falta" in resultado["erro"]


def test_ip_fora_do_lab_boundary_e_rejeitado(monkeypatch):
    monkeypatch.setattr(tool_dispatcher, "alvo_permitido", lambda ip: False)
    resultado = tool_dispatcher.dispatch(_tool_call("run_nmap", "8.8.8.8"))
    assert resultado["ok"] is False
    assert "fora do lab_boundary" in resultado["erro"]


def test_ip_dentro_do_lab_boundary_e_aceite(monkeypatch):
    monkeypatch.setattr(tool_dispatcher, "alvo_permitido", lambda ip: True)
    monkeypatch.setattr(
        tool_dispatcher, "ler_uma_vez_todas", lambda alvos: {"nmap": ["evento_fake"]}
    )
    resultado = tool_dispatcher.dispatch(_tool_call("run_nmap", "127.0.0.1"))
    assert resultado["ok"] is True
    assert resultado["ferramenta"] == "nmap"
    assert resultado["target"] == "127.0.0.1"


def test_tshark_ignora_alvo_proposto_pela_ia(monkeypatch):
    """A IA tenta impor um alvo (8.8.8.8) diferente da interface fixa
    - tem de ser sempre ignorado, o alvo real usado é sempre 'lo'."""
    monkeypatch.setattr(
        tool_dispatcher, "ler_uma_vez_todas", lambda alvos: {"tshark": ["evento_fake"]}
    )
    resultado = tool_dispatcher.dispatch(_tool_call("run_tshark", "8.8.8.8"))
    assert resultado["ok"] is True
    assert resultado["target"] == "lo"
