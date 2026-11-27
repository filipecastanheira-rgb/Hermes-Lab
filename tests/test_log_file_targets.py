"""suricata and zeek read one fixed log file each: /run_tool refuses any other path."""
import pytest

from hermes.purple import purple_api
from hermes.purple.purple_api import PurpleAPI
from hermes.tools.suricata.suricata_reader import EVE_PATH_DEFAULT
from hermes.tools.zeek.zeek_reader import CONN_LOG_DEFAULT

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
def no_model(monkeypatch):
    monkeypatch.setattr("hermes.core.hermes_intelligence.HermesIntelligence", NoModel)


@pytest.fixture
def tool_calls(monkeypatch):
    chamadas = []

    def fake(alvos):
        chamadas.append(alvos)
        return []

    monkeypatch.setattr(purple_api, "ler_uma_vez_todas", fake)
    return chamadas


def _run_tool(tool, target):
    api = PurpleAPI(
        commands=None, config=None, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=None, compression=None, webhooks=None, dashboard=None,
    )
    return api.app.test_client().post(
        "/run_tool", json={"tool": tool, "target": target}, headers=AUTH)


def _com_barra_dupla(caminho):
    return caminho.replace("/", "//", 1)


@pytest.mark.parametrize("tool,target", [
    ("suricata", "/etc/passwd"),
    ("suricata", "/var/log/suricata/../../../etc/passwd"),
    ("suricata", "eve.json"),
    ("suricata", "/tmp/eve.json"),
    ("suricata", EVE_PATH_DEFAULT + ".1"),
    ("suricata", CONN_LOG_DEFAULT),
    ("zeek", "/etc/passwd"),
    ("zeek", "/opt/zeek/logs/current/../../../../etc/hosts"),
    ("zeek", "conn.log"),
    ("zeek", "/tmp/conn.log"),
    ("zeek", EVE_PATH_DEFAULT),
])
def test_any_other_path_is_refused_visibly(tool_calls, tool, target):
    r = _run_tool(tool, target)

    assert r.status_code == 400
    assert "log file" in r.get_json()["error"]
    assert tool_calls == []


@pytest.mark.parametrize("tool,target", [
    ("suricata", EVE_PATH_DEFAULT),
    ("suricata", _com_barra_dupla(EVE_PATH_DEFAULT)),
    ("zeek", CONN_LOG_DEFAULT),
    ("zeek", _com_barra_dupla(CONN_LOG_DEFAULT)),
])
def test_the_default_file_is_still_read(tool_calls, tool, target):
    assert _run_tool(tool, target).status_code == 200
    assert tool_calls == [{tool: target}]
