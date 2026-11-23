"""Request bodies of the wrong shape must be refused with 400, never crash with 500."""
import pytest

from hermes.purple.purple_api import PurpleAPI
from hermes.purple.purple_commands import PurpleCommands
from hermes.purple.purple_config import PurpleConfig

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


class FakeCache:
    def guardar(self, chave, valor):
        pass


class FakeWebhooks:
    def enviar(self, evento):
        pass


class FakeCommandLogger:
    def escrever(self, mensagem):
        pass


def _api(tmp_path):
    cfg = PurpleConfig(ficheiro=str(tmp_path / "cfg" / "purple_config.json"))
    commands = PurpleCommands(config=cfg, logger=FakeCommandLogger(), alerts=FakeAlerts())
    return PurpleAPI(
        commands=commands, config=cfg, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=FakeCache(), compression=None, webhooks=FakeWebhooks(), dashboard=None,
    )


def _post(api, path, body):
    return api.app.test_client().post(path, json=body, headers=AUTH)


ROUTES = ["/auth/bootstrap", "/comando", "/alerta", "/config", "/run_tool"]


@pytest.mark.parametrize("path", ROUTES)
def test_json_body_that_is_not_an_object_is_refused(tmp_path, path):
    assert _post(_api(tmp_path), path, [1]).status_code == 400


@pytest.mark.parametrize("body", [{}, {"comando": None}, {"comando": 5}, {"comando": ["a"]}])
def test_comando_with_missing_or_non_string_command_is_refused(tmp_path, body):
    assert _post(_api(tmp_path), "/comando", body).status_code == 400


@pytest.mark.parametrize("body", [
    {"tool": 5, "target": "127.0.0.1"},
    {"tool": None, "target": "127.0.0.1"},
    {"tool": ["nmap"], "target": "127.0.0.1"},
    {"tool": "nmap", "target": 5},
    {"tool": "nmap", "target": None},
])
def test_run_tool_with_wrong_types_is_refused(tmp_path, body):
    assert _post(_api(tmp_path), "/run_tool", body).status_code == 400


@pytest.mark.parametrize("body", [{}, {"tool": "nmap"}, {"target": "127.0.0.1"}])
def test_run_tool_with_missing_field_is_refused(tmp_path, body):
    assert _post(_api(tmp_path), "/run_tool", body).status_code == 400


@pytest.mark.parametrize("body", [{"chave": ["x"], "valor": 1}, {"chave": {"a": 1}, "valor": 1}])
def test_config_with_non_string_key_is_refused(tmp_path, body):
    assert _post(_api(tmp_path), "/config", body).status_code == 400


def test_valid_command_still_works(tmp_path):
    assert _post(_api(tmp_path), "/comando", {"comando": "pausar_eventos"}).status_code == 200


def test_bootstrap_with_bad_nonce_is_still_403(tmp_path):
    assert _post(_api(tmp_path), "/auth/bootstrap", {"nonce": "x"}).status_code == 403
