"""POST /config must reject values the runtime cannot use and leave the file untouched."""
import json

import pytest

from hermes.purple.purple_api import PurpleAPI
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


def _api(tmp_path):
    cfg = PurpleConfig(ficheiro=str(tmp_path / "cfg" / "purple_config.json"))
    api = PurpleAPI(
        commands=None, config=cfg, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=FakeCache(), compression=None, webhooks=FakeWebhooks(), dashboard=None,
    )
    return api, cfg


def _on_disk(cfg):
    with open(cfg.ficheiro) as f:
        return json.load(f)


INVALID = [
    ("intervalo_heartbeat", "x"),
    ("intervalo_heartbeat", -1),
    ("intervalo_heartbeat", 0),
    ("intervalo_heartbeat", True),
    ("intervalo_heartbeat", 3601),
    ("intervalo_healthcheck", "x"),
    ("intervalo_metricas", -5),
    ("simulacao_eventos", "yes"),
    ("nivel_alerta_minimo", "BANANA"),
]

VALID = [
    ("intervalo_heartbeat", 5),
    ("intervalo_healthcheck", 30),
    ("intervalo_metricas", 60),
    ("simulacao_eventos", False),
    ("nivel_alerta_minimo", "ERROR"),
]


@pytest.mark.parametrize("chave,valor", INVALID)
def test_invalid_value_is_rejected_and_not_persisted(tmp_path, chave, valor):
    api, cfg = _api(tmp_path)
    before = _on_disk(cfg)

    r = api.app.test_client().post("/config", json={"chave": chave, "valor": valor}, headers=AUTH)

    assert r.status_code == 400
    assert _on_disk(cfg) == before


@pytest.mark.parametrize("chave,valor", VALID)
def test_valid_value_is_accepted_and_persisted(tmp_path, chave, valor):
    api, cfg = _api(tmp_path)

    r = api.app.test_client().post("/config", json={"chave": chave, "valor": valor}, headers=AUTH)

    assert r.status_code == 200
    assert _on_disk(cfg)[chave] == valor


def test_unknown_key_is_still_rejected(tmp_path):
    api, cfg = _api(tmp_path)

    r = api.app.test_client().post("/config", json={"chave": "nao_existe", "valor": 1}, headers=AUTH)

    assert r.status_code == 400


def test_config_object_refuses_invalid_value(tmp_path):
    _, cfg = _api(tmp_path)
    before = _on_disk(cfg)

    with pytest.raises(ValueError):
        cfg.atualizar("intervalo_heartbeat", "x")

    assert _on_disk(cfg) == before
