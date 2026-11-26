"""The API log keeps metadata about responses, rotates at a size limit and is private to the user."""
import json
import os
import stat

import pytest

from hermes.purple.purple_api_logger import PurpleAPILogger

LIMITE_DEFEITO = 5 * 1024 * 1024


@pytest.fixture
def umask_022():
    antigo = os.umask(0o022)
    yield
    os.umask(antigo)


def _linhas(caminho):
    with open(caminho) as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def _modo(caminho):
    return stat.S_IMODE(os.stat(caminho).st_mode)


def test_response_log_keeps_the_endpoint_but_not_the_body(tmp_path):
    log = tmp_path / "api.log"
    PurpleAPILogger(str(log)).log_resposta("/dashboard", {
        "alertas_recentes": [{"descricao": "Open port 22", "contexto": {"src_ip": "203.0.113.9"}}],
        "ultimo_relatorio": "private report",
    })

    texto = log.read_text()
    evento = _linhas(log)[0]
    assert evento["tipo"] == "resposta"
    assert evento["dados"]["endpoint"] == "/dashboard"
    for segredo in ("Open port 22", "203.0.113.9", "private report"):
        assert segredo not in texto


def test_response_log_records_the_size_of_the_body(tmp_path):
    log = tmp_path / "api.log"
    corpo = {"a": "é" * 10, "b": [1, 2, 3]}

    PurpleAPILogger(str(log)).log_resposta("/status", corpo)

    esperado = len(json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8"))
    assert _linhas(log)[0]["dados"]["bytes"] == esperado


@pytest.mark.parametrize("corpo", [[1, 2], "text", None, 5, {"novo_token": "abc"}])
def test_response_log_accepts_any_kind_of_body(tmp_path, corpo):
    log = tmp_path / "api.log"

    PurpleAPILogger(str(log)).log_resposta("/x", corpo)

    assert _linhas(log)[0]["dados"]["endpoint"] == "/x"
    assert "abc" not in log.read_text()


def test_calls_and_denials_are_still_logged_in_full(tmp_path):
    log = tmp_path / "api.log"
    logger = PurpleAPILogger(str(log))

    logger.log_chamada("/config", "POST", "tok", {"chave": "intervalo_heartbeat", "valor": 5}, utilizador="teste")
    logger.log_acesso_negado("/config", "Invalid key")

    chamada, negado = _linhas(log)
    assert chamada["dados"]["payload"] == {"chave": "intervalo_heartbeat", "valor": 5}
    assert chamada["dados"]["utilizador"] == "teste"
    assert negado["dados"]["motivo"] == "Invalid key"


def test_new_log_file_is_private(tmp_path, umask_022):
    log = tmp_path / "api.log"

    PurpleAPILogger(str(log)).log_acesso_negado("/e", "m")

    assert _modo(log) == 0o600


def test_existing_log_file_is_made_private(tmp_path, umask_022):
    log = tmp_path / "api.log"
    log.write_text("")
    os.chmod(log, 0o664)

    PurpleAPILogger(str(log)).log_acesso_negado("/e", "m")

    assert _modo(log) == 0o600


def test_default_limit_is_5_mib(tmp_path):
    assert PurpleAPILogger(str(tmp_path / "api.log")).max_bytes == LIMITE_DEFEITO


def test_log_rotates_at_the_size_limit(tmp_path):
    log = tmp_path / "api.log"
    logger = PurpleAPILogger(str(log), max_bytes=2000)

    for i in range(100):
        logger.log_acesso_negado("/e", f"m{i}")

    assert os.path.getsize(log) <= 2000
    assert os.path.exists(f"{log}.1")
    assert os.path.getsize(f"{log}.1") <= 2000
    assert not os.path.exists(f"{log}.2")


def test_rotation_keeps_the_newest_lines_without_gaps(tmp_path):
    log = tmp_path / "api.log"
    logger = PurpleAPILogger(str(log), max_bytes=2000)

    for i in range(100):
        logger.log_acesso_negado("/e", f"m{i}")

    motivos = [e["dados"]["motivo"] for e in _linhas(f"{log}.1") + _linhas(log)]
    assert motivos[-1] == "m99"
    assert len(motivos) < 100
    assert motivos == [f"m{i}" for i in range(100 - len(motivos), 100)]


def test_rotated_file_is_private(tmp_path, umask_022):
    log = tmp_path / "api.log"
    logger = PurpleAPILogger(str(log), max_bytes=2000)

    for i in range(100):
        logger.log_acesso_negado("/e", f"m{i}")

    assert _modo(f"{log}.1") == 0o600
    assert _modo(log) == 0o600


def test_a_line_bigger_than_the_limit_is_still_written(tmp_path):
    log = tmp_path / "api.log"

    PurpleAPILogger(str(log), max_bytes=50).log_acesso_negado("/e", "x" * 500)

    assert _linhas(log)[0]["dados"]["motivo"] == "x" * 500


def test_an_existing_file_over_the_limit_is_rotated_on_the_first_write(tmp_path):
    log = tmp_path / "api.log"
    log.write_text("x" * 5000 + "\n")

    PurpleAPILogger(str(log), max_bytes=2000).log_acesso_negado("/e", "first")

    assert os.path.getsize(f"{log}.1") >= 5000
    assert [e["dados"]["motivo"] for e in _linhas(log)] == ["first"]
