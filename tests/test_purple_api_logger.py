"""Tokens em claro nunca vao para o log nem para o ficheiro de estado.

Um log com tokens e um segredo em disco: e copiado, enviado por email para
debug, arquivado em backups. O mesmo para `config/purple_ratelimit.json`, que
guardava o token como chave JSON. Estes testes fixam a regra: aparece apenas
`token_ref`, um resumo SHA-256 truncado que permite correlacionar pedidos sem
permitir reconstruir o token.
"""
import json

from hermes.purple.purple_api_logger import PurpleAPILogger, token_ref
from hermes.purple.purple_ratelimit import PurpleRateLimit

SEGREDO = "lab_3f9c2b7a-token-muito-secreto"


def eventos(ficheiro):
    return [json.loads(linha) for linha in ficheiro.read_text().splitlines() if linha.strip()]


def test_token_ref_e_estavel_truncado_e_nao_reversivel():
    assert token_ref(SEGREDO) == token_ref(SEGREDO)
    assert token_ref(SEGREDO) != token_ref("outro-token")
    assert len(token_ref(SEGREDO)) == 12
    assert SEGREDO not in token_ref(SEGREDO)
    assert token_ref(None) is None


def test_log_chamada_nao_guarda_o_token(tmp_path):
    ficheiro = tmp_path / "api.log"
    PurpleAPILogger(str(ficheiro)).log_chamada("/status", "GET", SEGREDO, {"x": 1})

    assert SEGREDO not in ficheiro.read_text()
    dados = eventos(ficheiro)[0]["dados"]
    assert dados["token_ref"] == token_ref(SEGREDO)
    assert "token" not in dados, "o campo tem de se chamar token_ref, nao token"


def test_log_erro_autenticacao_nao_guarda_o_token(tmp_path):
    ficheiro = tmp_path / "api.log"
    PurpleAPILogger(str(ficheiro)).log_erro_autenticacao("/status", SEGREDO)

    assert SEGREDO not in ficheiro.read_text()
    dados = eventos(ficheiro)[0]["dados"]
    assert dados["token_ref"] == token_ref(SEGREDO)
    assert dados["token_presente"] is True


def test_log_erro_autenticacao_regista_tentativa_sem_token(tmp_path):
    ficheiro = tmp_path / "api.log"
    PurpleAPILogger(str(ficheiro)).log_erro_autenticacao("/status", None)

    dados = eventos(ficheiro)[0]["dados"]
    assert dados["token_ref"] is None
    assert dados["token_presente"] is False


def test_log_token_regenerado_nao_guarda_o_token_novo(tmp_path):
    """O pior caso: escrever o token novo, valido, no log de rotacao."""
    ficheiro = tmp_path / "api.log"
    PurpleAPILogger(str(ficheiro)).log_token_regenerado(SEGREDO)

    assert SEGREDO not in ficheiro.read_text()
    assert eventos(ficheiro)[0]["dados"]["token_ref"] == token_ref(SEGREDO)


def test_ficheiro_do_rate_limit_nao_guarda_o_token(tmp_path):
    ficheiro = tmp_path / "ratelimit.json"
    rl = PurpleRateLimit(ficheiro=str(ficheiro))

    assert rl.verificar_token(SEGREDO) is True
    assert rl.verificar_token(SEGREDO) is True

    texto = ficheiro.read_text()
    assert SEGREDO not in texto
    chaves = list(json.loads(texto)["tokens"].keys())
    assert len(chaves) == 1, "o mesmo token tem de produzir a mesma chave"
    assert len(chaves[0]) == 16
