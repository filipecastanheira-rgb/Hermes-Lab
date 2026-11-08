"""The exact shapes of request the dashboard sends, at the Flask level."""
from flask import Flask

from hermes.purple.purple_api import PurpleAPI

JSON_HEADERS = {"Content-Type": "application/json"}


class FakeAlerts:
    def emitir_alerta(self, **kwargs):
        return {}


class FakeAuth:
    def validar(self, recebido):
        return {"id": "id-teste", "nome": "teste"} if recebido == "bom" else None


class FakeApiLogger:
    def __init__(self):
        self.chamadas = []

    def log_chamada(self, endpoint, metodo, token, payload, utilizador=None):
        self.chamadas.append({"endpoint": endpoint, "payload": payload})

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


class FakeDashboard:
    def gerar_dashboard(self):
        return {"estado": "ok", "metricas": {}, "alertas_recentes": []}


def _api():
    return PurpleAPI(
        commands=None, config=None, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=None, compression=None, webhooks=None, dashboard=FakeDashboard(),
    )


def _client_with_session(api):
    client = api.app.test_client()
    nonce = api.bootstrap.novo_nonce()
    assert client.post("/auth/bootstrap", json={"nonce": nonce}).status_code == 200
    return client


def test_get_com_cookie_e_content_type_sem_corpo_responde_200():
    api = _api()
    client = _client_with_session(api)

    assert client.get("/dashboard", headers=JSON_HEADERS).status_code == 200


def test_get_com_cabecalho_e_content_type_sem_corpo_responde_200():
    client = _api().app.test_client()

    r = client.get("/dashboard", headers={**JSON_HEADERS, "X-Hermes-Token": "bom"})

    assert r.status_code == 200


def test_corpo_json_invalido_nao_da_400_vindo_do_logger():
    """An unparseable body must be logged as empty, not turn the request into a 400."""
    api = _api()
    app = Flask("teste")

    def rota():
        return {"ok": True}

    app.add_url_rule("/x", "x", PurpleAPI._require_token(api, rota), methods=["POST"])
    client = app.test_client()

    r = client.post("/x", data="{isto nao e json",
                    headers={"Content-Type": "application/json", "X-Hermes-Token": "bom"})

    assert r.status_code == 200
    assert api.api_logger.chamadas[-1]["payload"] == {}


def _rota_post(api):
    from flask import Flask

    app = Flask("teste")

    def rota():
        return {"ok": True}

    app.add_url_rule("/x", "x", PurpleAPI._require_token(api, rota), methods=["POST"])
    return app.test_client()


def test_cookie_com_origem_estranha_em_post_e_recusada():
    api = _api()
    _client_with_session(api)
    client = _rota_post(api)
    client.set_cookie("hermes_session", list(api.bootstrap.sessoes)[0], domain="localhost")

    r = client.post("/x", headers={"Origin": "http://evil.example"})

    assert r.status_code == 403


def test_cookie_com_a_origem_do_servidor_e_aceite():
    api = _api()
    _client_with_session(api)
    client = _rota_post(api)
    client.set_cookie("hermes_session", list(api.bootstrap.sessoes)[0], domain="localhost")

    assert client.post("/x", headers={"Origin": "http://localhost"}).status_code == 200


def test_token_sem_origem_continua_a_funcionar():
    api = _api()
    client = _rota_post(api)

    assert client.post("/x", headers={"X-Hermes-Token": "bom"}).status_code == 200
