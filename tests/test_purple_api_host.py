"""So nomes locais no cabecalho Host (defesa contra DNS rebinding).

O cenario: um dominio controlado pelo atacante resolve para 127.0.0.1. O
browser da vitima liga-se a este servidor, mas envia esse dominio no Host. A
app nao tem nada a ganhar em aceitar nomes que nao sejam locais - e aceita-los
e o que permite a um site externo falar com a API local.
"""
import pytest

from hermes.purple.purple_api import PurpleAPI, host_permitido


class FakeAlerts:
    def emitir_alerta(self, **kwargs):
        return {}


class FakeAuth:
    def validar(self, recebido):
        return {"id": "id-de-teste", "nome": "bom"} if recebido == "bom" else None


class FakeApiLogger:
    def log_chamada(self, **kwargs):
        pass

    def log_acesso_negado(self, *a, **k):
        pass

    def log_erro_autenticacao(self, *a, **k):
        pass


class FakeRateLimit:
    def verificar_ip(self, ip):
        return True

    def verificar_token(self, token):
        return True


@pytest.mark.parametrize("host", [
    "localhost",
    "localhost:5000",
    "LOCALHOST:8080",
    "127.0.0.1",
    "127.0.0.1:5000",
    "127.0.0.1:65535",
    "[::1]:5000",
])
def test_hosts_locais_sao_aceites(host):
    assert host_permitido(host) is True


@pytest.mark.parametrize("host", [
    "[::1]xyz",
    "[::1]:5000lixo",
    "127.0.0.1:",
    "127.0.0.1:abc",
    "127.0.0.1:123456",
    "127.0.0.1:\u0665",
    "127.0.0.1:\u00b2",
    "localhost:99999",
    "127.0.0.1:65536",
    "::1",
    " localhost",
    "localhost\t",
    "evil.example",
    "evil.example:5000",
    "localhost.evil.com",
    "127.0.0.1.nip.io",
    "127.0.0.1.attacker.net:5000",
    "",
    None,
])
def test_hosts_desconhecidos_sao_recusados(host):
    assert host_permitido(host) is False


def _client():
    api = PurpleAPI(
        commands=None, config=None, metrics=None, alerts=FakeAlerts(), logger=None,
        auth=FakeAuth(), api_logger=FakeApiLogger(), ratelimit=FakeRateLimit(),
        cache=None, compression=None, webhooks=None, dashboard=object(),
    )
    return api.app.test_client()


def test_pedido_com_host_local_passa():
    assert _client().get("/dashboard/view").status_code == 200


def test_pedido_com_host_estranho_e_recusado():
    r = _client().get("/dashboard/view", headers={"Host": "evil.example"})
    assert r.status_code == 400


def test_host_estranho_e_recusado_antes_de_qualquer_autenticacao():
    """Mesmo com um token valido, um Host estranho nao chega a ser avaliado."""
    r = _client().get("/dashboard", headers={"Host": "evil.example", "X-Hermes-Token": "bom"})
    assert r.status_code == 400
