"""An oversized target must be refused visibly by /run_tool and by the AI dispatcher."""
import pytest

from hermes.core import lab_boundary as lb
from hermes.core import tool_dispatcher
from hermes.purple import purple_api
from hermes.purple.purple_api import PurpleAPI

AUTH = {"X-Hermes-Token": "bom"}


class FakeAlerts:
    def emitir_alerta(self, **kwargs):
        return {}


class FakeAuth:
    def validar(self, recebido):
        return {"id": "id-teste", "nome": "teste"} if recebido == "bom" else None


class FakeApiLogger:
    def log_chamada(self, *a, **k):
        pass

    def log_acesso_negado(self, *a, **k):
        pass

    def log_erro_autenticacao(self, *a, **k):
        pass

    def log_resposta(self, *a, **k):
        pass


class FakeRateLimit:
    def verificar_ip(self, ip):
        return True

    def verificar_token(self, token):
        return True


class NoModel:
    def __init__(self, *a, **k):
        raise RuntimeError("no model in tests")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(lb, "CONFIG_PATH", str(tmp_path / "none.json"))
    monkeypatch.setattr("hermes.core.hermes_intelligence.HermesIntelligence", NoModel)


@pytest.fixture
def tool_calls(monkeypatch):
    chamadas = []

    def fake(alvos):
        chamadas.append(alvos)
        return []

    monkeypatch.setattr(purple_api, "ler_uma_vez_todas", fake)
    monkeypatch.setattr(tool_dispatcher, "ler_uma_vez_todas", fake)
    return chamadas


def _api():
    return PurpleAPI(
        commands=None, config=None, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=None, compression=None, webhooks=None, dashboard=None,
    )


def _run_tool(tool, target):
    return _api().app.test_client().post(
        "/run_tool", json={"tool": tool, "target": target}, headers=AUTH)


@pytest.mark.parametrize("tool", ["nmap", "openvas"])
@pytest.mark.parametrize("target", ["127.0.0.0/8", "127.0.0.0/23"])
def test_run_tool_refuses_an_oversized_target_visibly(tool_calls, tool, target):
    r = _run_tool(tool, target)

    assert r.status_code == 400
    assert "too large" in r.get_json()["error"]
    assert tool_calls == []


@pytest.mark.parametrize("tool,target", [
    ("nmap", "127.0.0.1"), ("nmap", "127.0.0.0/24"), ("openvas", "127.0.0.1"),
])
def test_run_tool_still_runs_a_small_target(tool_calls, tool, target):
    assert _run_tool(tool, target).status_code == 200
    assert tool_calls == [{tool: target}]


def test_run_tool_size_limit_does_not_apply_to_an_interface(tool_calls):
    assert _run_tool("tshark", "lo").status_code == 200
    assert tool_calls == [{"tshark": "lo"}]


def _call(nome, target):
    return {"function": {"name": nome, "arguments": {"target": target}}}


@pytest.mark.parametrize("nome", ["run_nmap", "run_openvas"])
@pytest.mark.parametrize("target", ["127.0.0.0/8", "127.0.0.0/23"])
def test_dispatch_refuses_an_oversized_target(tool_calls, nome, target):
    r = tool_dispatcher.dispatch(_call(nome, target))

    assert r["ok"] is False
    assert "too large" in r["erro"]
    assert tool_calls == []


@pytest.mark.parametrize("nome,target", [
    ("run_nmap", "127.0.0.1"), ("run_openvas", "127.0.0.1"), ("run_tshark", "ignored"),
])
def test_dispatch_still_runs_a_small_target(tool_calls, nome, target):
    assert tool_dispatcher.dispatch(_call(nome, target))["ok"] is True
    assert len(tool_calls) == 1
