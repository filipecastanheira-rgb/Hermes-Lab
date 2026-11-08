"""Entrada local sem token: nonce de uso unico trocado por cookie HttpOnly.

O que estes testes fixam, e que e a parte facil de fazer mal:

- o nonce vale **uma vez** e e consumido mesmo quando a tentativa falha;
- expira;
- so funciona a partir de loopback;
- a cookie so serve enquanto o servidor a conhecer (reiniciar invalida);
- sem cookie e sem cabecalho nao se entra.
"""
import pytest

from hermes.purple.purple_api import Bootstrap, PurpleAPI

NONCE = "a" * 64


class FakeAlerts:
    def emitir_alerta(self, **kwargs):
        return {}


class FakeAuth:
    def validar(self, recebido):
        return {"id": "id-teste", "nome": "teste"} if recebido == "bom" else None


class FakeApiLogger:
    def __init__(self):
        self.negados = []
        self.chamadas = []

    def log_chamada(self, endpoint, metodo, token, payload, utilizador=None):
        self.chamadas.append({"endpoint": endpoint, "utilizador": utilizador})

    def log_acesso_negado(self, endpoint, motivo):
        self.negados.append({"endpoint": endpoint, "motivo": motivo})

    def log_erro_autenticacao(self, endpoint, token):
        pass

    def log_resposta(self, endpoint, resposta):
        pass


class FakeRateLimit:
    def verificar_ip(self, ip):
        return True

    def verificar_token(self, token):
        return True


class FakeDashboard:
    def gerar_dashboard(self):
        return {"estado": "ok", "metricas": {}, "alertas_recentes": []}


def _client():
    api = PurpleAPI(
        commands=None, config=None, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=None, compression=None, webhooks=None, dashboard=FakeDashboard(),
    )
    return api, api.app.test_client()


def _bootstrap(client, nonce, **kw):
    return client.post("/auth/bootstrap", json={"nonce": nonce}, **kw)


# ------------------------------------------------------------------ Bootstrap


def test_nonce_vale_uma_vez():
    b = Bootstrap()
    nonce = b.novo_nonce()
    assert b.trocar(nonce, "127.0.0.1")
    assert b.trocar(nonce, "127.0.0.1") is None


def test_nonce_e_consumido_mesmo_quando_falha():
    b = Bootstrap()
    nonce = b.novo_nonce()
    assert b.trocar("errado", "127.0.0.1") is None
    # a tentativa errada queimou o nonce, senao podia-se tentar ate acertar
    assert b.trocar(nonce, "127.0.0.1") is None


def test_nonce_expira():
    b = Bootstrap()
    nonce = b.novo_nonce()
    b.emitido_em -= b.TTL + 1
    assert b.trocar(nonce, "127.0.0.1") is None


def test_nonce_so_em_loopback():
    b = Bootstrap()
    nonce = b.novo_nonce()
    assert b.trocar(nonce, "10.0.0.5") is None


def test_nonce_nao_ascii_e_consumido_sem_erro():
    b = Bootstrap()
    nonce = b.novo_nonce()
    assert b.trocar("n\u00e3o-ascii-\u0663", "127.0.0.1") is None
    # a tentativa queimou o nonce, tal como qualquer outra tentativa errada
    assert b.trocar(nonce, "127.0.0.1") is None


# ------------------------------------------------------------------ rotas


def test_bootstrap_valido_devolve_cookie():
    api, client = _client()
    nonce = api.bootstrap.novo_nonce()

    r = _bootstrap(client, nonce)

    assert r.status_code == 200
    cookie = r.headers.get("Set-Cookie", "")
    assert "hermes_session=" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie


def test_bootstrap_com_nonce_errado_recusa():
    api, client = _client()
    api.bootstrap.novo_nonce()
    assert _bootstrap(client, "b" * 64).status_code == 403


def test_bootstrap_fora_de_loopback_recusa():
    api, client = _client()
    nonce = api.bootstrap.novo_nonce()
    r = _bootstrap(client, nonce, environ_base={"REMOTE_ADDR": "10.0.0.5"})
    assert r.status_code == 403


def test_cookie_da_acesso_a_api():
    api, client = _client()
    assert client.get("/dashboard").status_code == 403  # sem cookie

    _bootstrap(client, api.bootstrap.novo_nonce())
    r = client.get("/dashboard")

    assert r.status_code == 200
    assert r.get_json()["estado"] == "ok"


def test_cookie_que_o_servidor_nao_conhece_e_recusada():
    _, client = _client()
    client.set_cookie("hermes_session", "sid-inventado", domain="localhost")
    assert client.get("/dashboard").status_code == 403


def test_logout_revoga_a_sessao():
    api, client = _client()
    _bootstrap(client, api.bootstrap.novo_nonce())
    assert client.get("/dashboard").status_code == 200

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/dashboard").status_code == 403


def test_reiniciar_o_servidor_invalida_as_sessoes():
    api, client = _client()
    _bootstrap(client, api.bootstrap.novo_nonce())

    # um "novo arranque" e um Bootstrap novo: as sessoes vivem em memoria
    api.bootstrap = Bootstrap()
    assert client.get("/dashboard").status_code == 403


def test_cabecalho_continua_a_funcionar_sem_cookie():
    _, client = _client()
    r = client.get("/dashboard", headers={"X-Hermes-Token": "bom"})
    assert r.status_code == 200



def test_bootstrap_com_nonce_nao_ascii_recusa_com_403():
    api, client = _client()
    api.bootstrap.novo_nonce()
    assert _bootstrap(client, "n\u00e3o-ascii-\u0663").status_code == 403
