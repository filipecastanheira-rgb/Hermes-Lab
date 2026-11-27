"""The tshark target is a network interface name: anything else is refused before a capture starts."""
import pytest

from hermes.core import lab_boundary as lb
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


def _run_tool(target):
    api = PurpleAPI(
        commands=None, config=None, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=None, compression=None, webhooks=None, dashboard=None,
    )
    return api.app.test_client().post(
        "/run_tool", json={"tool": "tshark", "target": target}, headers=AUTH)


@pytest.mark.parametrize("nome", [
    "lo", "eth0", "wlan0", "enp0s3", "br-1a2b3c", "docker0", "eth0.100", "wg_hermes",
])
def test_real_interface_names_are_valid(nome):
    assert lb.interface_valida(nome) is True


@pytest.mark.parametrize("nome", [
    "-", "-x", "--version", "rpcap://host/eth0", "/tmp/pipe", "", "a" * 16,
    "eth 0", "eth0;ls", "$(id)", "eth0\n", " eth0", None, 5,
])
def test_anything_that_is_not_an_interface_name_is_refused(nome):
    assert lb.interface_valida(nome) is False


@pytest.mark.parametrize("alvo", ["-x", "/tmp/pipe", "rpcap://h/e", "eth0;ls"])
def test_run_tool_refuses_a_bad_interface_visibly(tool_calls, alvo):
    r = _run_tool(alvo)

    assert r.status_code == 400
    assert "interface" in r.get_json()["error"]
    assert tool_calls == []


@pytest.mark.parametrize("alvo", ["lo", "eth0"])
def test_run_tool_still_runs_a_real_interface(tool_calls, alvo):
    assert _run_tool(alvo).status_code == 200
    assert tool_calls == [{"tshark": alvo}]


def test_reader_does_not_start_a_capture_on_a_bad_interface(monkeypatch):
    import hermes.tools.tshark.tshark_reader as reader
    capturas = []

    class Fake:
        def capturar(self, interface, count):
            capturas.append(interface)
            return []

    monkeypatch.setattr(reader, "TSharkTool", Fake)

    assert reader.ler_uma_vez("-x") == []
    assert reader.ler_uma_vez("/tmp/pipe") == []
    assert capturas == []


def test_reader_still_captures_on_a_real_interface(monkeypatch):
    import hermes.tools.tshark.tshark_reader as reader
    capturas = []

    class Fake:
        def capturar(self, interface, count):
            capturas.append(interface)
            return []

    monkeypatch.setattr(reader, "TSharkTool", Fake)

    reader.ler_uma_vez("lo")

    assert capturas == ["lo"]
