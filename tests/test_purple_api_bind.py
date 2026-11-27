"""A API so arranca em loopback - e recusa arrancar de outra forma.

A maquina corre outros servicos e tem ligacao a internet. O bind em 127.0.0.1
e o controlo que impede a API de ficar exposta; se estivesse apenas escrito
como string dentro de `app.run()`, uma alteracao descuidada (ou uma ferramenta
que reescreva o ficheiro) expunha o servico em silencio. Aqui o bind e uma
invariante verificada: falha no arranque, ruidosamente.
"""
import pytest

from hermes.purple.purple_api import HOST_BIND, endereco_bind


def test_bind_por_omissao_e_loopback():
    assert HOST_BIND == "127.0.0.1"
    assert endereco_bind() == "127.0.0.1"


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_loopback_explicito_e_aceite(host):
    assert endereco_bind(host) == host


@pytest.mark.parametrize("host", [
    "0.0.0.0",              # todas as interfaces: o acidente classico
    "192.168.1.10",         # a typical LAN address
    "10.0.0.5",
    "localhost",            # nome, nao endereco: depende do resolver
    "",
])
def test_bind_aberto_e_recusado(host):
    with pytest.raises(ValueError):
        endereco_bind(host)


def test_iniciar_passa_pelo_guard(monkeypatch):
    """Se alguem trocar o host em `iniciar()`, este teste apanha."""
    from hermes.purple.purple_api import PurpleAPI

    class _Noop:
        def __getattr__(self, name):
            return lambda *a, **k: None

    api = PurpleAPI(
        commands=_Noop(), config=_Noop(), metrics=_Noop(), alerts=_Noop(), logger=_Noop(),
        auth=_Noop(), api_logger=_Noop(), ratelimit=_Noop(), cache=_Noop(),
        compression=_Noop(), webhooks=_Noop(), dashboard=_Noop(),
    )

    capturado = {}
    monkeypatch.setattr(api.app, "run", lambda **kw: capturado.update(kw))
    api.iniciar(porta=5099)

    assert capturado["host"] == "127.0.0.1"
    assert capturado["port"] == 5099
