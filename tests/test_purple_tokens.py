"""Token management helpers, called by the CLI."""
import pytest

from hermes.purple.purple_auth import PurpleAuth
from hermes.purple import purple_tokens as T


@pytest.fixture
def store(tmp_path):
    return PurpleAuth(str(tmp_path / "purple_auth.json"))


def test_criar_devolve_id_e_token_utilizavel(store):
    token_id, token = T.criar(store, "kali")

    assert token_id
    identidade = store.validar(token)
    assert identidade and identidade["id"] == token_id
    assert identidade["nome"] == "kali"


def test_listar_nao_expoe_tokens_nem_resumos(store):
    _, token = T.criar(store, "telemovel")

    listagem = T.listar(store)
    texto = T.formatar_lista(listagem)

    assert token not in texto
    assert all("hash" not in t for t in listagem)
    assert "telemovel" in texto


def test_revogar_invalida_apenas_o_indicado(store):
    id_a, token_a = T.criar(store, "a")
    _, token_b = T.criar(store, "b")

    assert T.revogar(store, id_a) is True
    assert store.validar(token_a) is None
    assert store.validar(token_b) is not None


def test_revogar_id_inexistente_devolve_false(store):
    assert T.revogar(store, "nao-existe") is False


def test_lista_vazia_tem_mensagem_propria():
    assert T.formatar_lista([]) == "No tokens configured."
