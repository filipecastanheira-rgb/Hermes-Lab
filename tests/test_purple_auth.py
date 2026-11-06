"""O token so e aceite no cabecalho X-Hermes-Token - nunca na URL.

Estes testes fixam o invariante que o dashboard passou a depender: um token
na query string e recusado (mesmo que seja valido) e a tentativa fica
registada. Sem isto, bastaria reabrir /dashboard/view?token=... para voltar ao
comportamento antigo e o token voltava a aparecer no historico do browser, no
Referer e nos logs de acesso do servidor.
"""
import pytest
from flask import Flask

from hermes.purple.purple_api import PurpleAPI

TOKEN = "token-de-teste-123"


class FakeAuth:
    def __init__(self):
        self.recebidos = []

    def validar(self, recebido):
        self.recebidos.append(recebido)
        return recebido == TOKEN


class FakeApiLogger:
    def __init__(self):
        self.chamadas = []
        self.negados = []
        self.falhas_auth = []

    def log_chamada(self, endpoint, metodo, token, payload):
        self.chamadas.append({"endpoint": endpoint, "metodo": metodo, "token": token})

    def log_acesso_negado(self, endpoint, motivo):
        self.negados.append({"endpoint": endpoint, "motivo": motivo})

    def log_erro_autenticacao(self, endpoint, token):
        self.falhas_auth.append({"endpoint": endpoint, "token": token})


class FakeRateLimit:
    def verificar_ip(self, ip):
        return True

    def verificar_token(self, token):
        return True


class FakeAlerts:
    def __init__(self):
        self.emitidos = []

    def emitir_alerta(self, severidade, origem, descricao, contexto=None):
        self.emitidos.append({"severidade": severidade, "origem": origem,
                              "descricao": descricao, "contexto": contexto})
        return {}


class StubAPI:
    """PurpleAPI sem Flask nem dependencias reais: so o que _require_token usa.

    Os dois metodos sao os verdadeiros, ligados a esta classe, para que o
    "self" seja um objeto real e nao um SimpleNamespace sem os metodos.
    """

    _require_token = PurpleAPI._require_token
    _recusar_token_na_url = PurpleAPI._recusar_token_na_url

    def __init__(self):
        self.auth = FakeAuth()
        self.api_logger = FakeApiLogger()
        self.ratelimit = FakeRateLimit()
        self.alerts = FakeAlerts()


@pytest.fixture
def ctx():
    stub = StubAPI()
    app = Flask(__name__)

    def protegido():
        return {"ok": True}

    # _require_token(self, func) e um metodo normal: aplicado a mao porque o
    # "self" e um stub e nao uma instancia real de PurpleAPI.
    app.add_url_rule("/protegido", "protegido", PurpleAPI._require_token(stub, protegido))

    return stub, app.test_client()


def test_cabecalho_valido_autoriza(ctx):
    stub, client = ctx
    r = client.get("/protegido", headers={"X-Hermes-Token": TOKEN})
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}
    assert stub.api_logger.chamadas and stub.api_logger.chamadas[0]["token"] == TOKEN


def test_sem_token_e_recusado(ctx):
    stub, client = ctx
    r = client.get("/protegido")
    assert r.status_code == 403
    assert stub.api_logger.falhas_auth == [{"endpoint": "/protegido", "token": None}]
    # um pedido rejeitado nao conta como chamada autenticada
    assert stub.api_logger.chamadas == []


def test_token_invalido_e_recusado(ctx):
    stub, client = ctx
    r = client.get("/protegido", headers={"X-Hermes-Token": "errado"})
    assert r.status_code == 403
    assert stub.api_logger.falhas_auth == [{"endpoint": "/protegido", "token": "errado"}]
    assert stub.api_logger.chamadas == []


def test_token_na_url_e_recusado_mesmo_valido(ctx):
    stub, client = ctx
    r = client.get(f"/protegido?token={TOKEN}")
    assert r.status_code == 403
    # nao chega a ser tratado como pedido autenticado
    assert stub.api_logger.chamadas == []
    # fica registado como acesso negado, com um alerta
    assert any("query string" in n["motivo"] for n in stub.api_logger.negados)
    assert len(stub.alerts.emitidos) == 1
    assert stub.alerts.emitidos[0]["severidade"] == "MEDIO"


def test_token_na_url_nao_e_anulado_pelo_cabecalho(ctx):
    """Ter o cabecalho valido nao pode servir de desculpa para aceitar a URL."""
    stub, client = ctx
    r = client.get(f"/protegido?token={TOKEN}", headers={"X-Hermes-Token": TOKEN})
    assert r.status_code == 403


def test_token_da_url_nao_fica_em_logs(ctx):
    stub, client = ctx
    client.get(f"/protegido?token={TOKEN}")
    registado = [c["token"] for c in stub.api_logger.chamadas]
    assert TOKEN not in registado, "o token da URL nao deve ser copiado para os logs"


def test_outros_parametros_na_url_nao_estorvam(ctx):
    stub, client = ctx
    r = client.get("/protegido?outra=coisa", headers={"X-Hermes-Token": TOKEN})
    assert r.status_code == 200


# ------------------------------------------------------ a casca do dashboard


def test_casca_do_dashboard_nao_leva_placeholder_de_token():
    """Se alguem voltar a injectar o token no HTML, este teste falha."""
    from hermes.purple.purple_api import _DASHBOARD_HTML

    assert "__TOKEN__" not in _DASHBOARD_HTML
    assert "sessionStorage" in _DASHBOARD_HTML


def test_dashboard_view_e_servida_sem_autenticacao_e_sem_token():
    """A casca tem de abrir no browser: sem cabecalho e sem token."""
    api = PurpleAPI(
        commands=None, config=None, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=None, compression=None, webhooks=None, dashboard=object(),
    )
    client = api.app.test_client()

    r = client.get("/dashboard/view")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "__TOKEN__" not in html
    assert "sessionStorage" in html

    # e a mesma rota com ?token= continua a ser recusada
    assert client.get("/dashboard/view?token=abc").status_code == 403
