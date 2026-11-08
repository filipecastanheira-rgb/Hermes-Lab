"""Tokens guardados so como resumo; varios tokens, um por pessoa.

O ficheiro `config/purple_auth.json` guardava o token em claro e um unico
token para toda a gente. Isso tem dois problemas: quem le o ficheiro entra, e
nao e possivel dar acesso a uma pessoa sem dar acesso a todas (nem revogar uma
sem revogar as outras).
"""
import json

import pytest

from hermes.purple.purple_auth import FORMATO, PurpleAuth, hash_token

TOKEN = "token-de-teste-123"


def test_primeiro_arranque_cria_token_e_nao_o_guarda_em_claro(tmp_path):
    ficheiro = tmp_path / "purple_auth.json"
    auth = PurpleAuth(str(ficheiro))

    assert auth.token_inicial
    assert auth.validar(auth.token_inicial)["nome"] == "cli"

    texto = ficheiro.read_text()
    assert auth.token_inicial not in texto
    assert hash_token(auth.token_inicial) in texto
    dados = json.loads(texto)
    assert dados["formato"] == FORMATO
    assert "token" not in dados, "o formato 1 (token em claro) nao pode voltar"


def test_validar_devolve_identidade_e_recusa_o_errado(tmp_path):
    auth = PurpleAuth(str(tmp_path / "a.json"))
    token = auth.criar("kali")

    identidade = auth.validar(token)
    assert identidade["nome"] == "kali" and identidade["id"]
    assert auth.validar("errado") is None
    assert auth.validar("") is None


def test_tokens_sao_independentes(tmp_path):
    auth = PurpleAuth(str(tmp_path / "a.json"))
    do_filipe = auth.criar("filipe")
    do_amigo = auth.criar("amigo")

    assert auth.validar(do_filipe)["nome"] == "filipe"
    assert auth.validar(do_amigo)["nome"] == "amigo"

    # revogar um nao afeta o outro
    assert auth.revogar(auth.validar(do_amigo)["id"]) is True
    assert auth.validar(do_amigo) is None
    assert auth.validar(do_filipe)["nome"] == "filipe"


def test_regenerar_invalida_o_antigo_e_mantem_o_nome(tmp_path):
    auth = PurpleAuth(str(tmp_path / "a.json"))
    antigo = auth.criar("telemovel")
    token_id = auth.validar(antigo)["id"]

    novo = auth.regenerar(token_id)

    assert novo and novo != antigo
    assert auth.validar(antigo) is None
    assert auth.validar(novo)["nome"] == "telemovel"


def test_regenerar_id_desconhecido_devolve_none(tmp_path):
    auth = PurpleAuth(str(tmp_path / "a.json"))
    assert auth.regenerar("nao-existe") is None


def test_listar_nao_expoe_resumos_nem_tokens(tmp_path):
    auth = PurpleAuth(str(tmp_path / "a.json"))
    token = auth.criar("x")

    listagem = auth.listar()
    assert listagem and all("hash" not in t for t in listagem)
    assert token not in json.dumps(listagem)


def test_migracao_do_formato_1_mantem_o_token_valido(tmp_path):
    """Um ficheiro antigo com token em claro continua a funcionar, sem o manter."""
    ficheiro = tmp_path / "purple_auth.json"
    ficheiro.write_text(json.dumps({
        "token": TOKEN,
        "criado_em": "Mon Jan 1 00:00:00 2026",
        "descricao": "Token inicial gerado automaticamente.",
    }))

    auth = PurpleAuth(str(ficheiro))

    assert auth.validar(TOKEN)["nome"] == "migrado"
    texto = ficheiro.read_text()
    assert TOKEN not in texto
    assert json.loads(texto)["formato"] == FORMATO


def test_ficheiro_e_criado_com_permissoes_restritas(tmp_path):
    ficheiro = tmp_path / "purple_auth.json"
    PurpleAuth(str(ficheiro))
    assert (ficheiro.stat().st_mode & 0o777) == 0o600


def test_token_publico_conhecido_nao_e_migrado(tmp_path):
    """sha256("hermes-default") e publico: migra-lo mantinha o acesso aberto."""
    from hermes.purple.purple_auth import TOKEN_PUBLICO_CONHECIDO

    ficheiro = tmp_path / "purple_auth.json"
    ficheiro.write_text(json.dumps({"token": TOKEN_PUBLICO_CONHECIDO}))

    auth = PurpleAuth(str(ficheiro))

    assert auth.validar(TOKEN_PUBLICO_CONHECIDO) is None
    assert auth.token_inicial, "tem de emitir um token novo e mostra-lo uma vez"
    assert auth.validar(auth.token_inicial) is not None
