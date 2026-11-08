"""Sessions have an absolute deadline, a cap, and the nonce exchange is atomic."""
import threading
import time

from hermes.purple.purple_api import Bootstrap


def _sessao(boot):
    boot.novo_nonce()
    sid = boot.trocar(boot.nonce, "127.0.0.1")
    assert sid
    return sid


def test_sessao_expira_pelo_prazo_absoluto():
    boot = Bootstrap()
    sid = _sessao(boot)
    assert boot.sessao_valida(sid)

    boot.sessoes[sid]["criada_em"] -= boot.SESSAO_TTL + 1

    assert boot.sessao_valida(sid) is False
    assert sid not in boot.sessoes, "a sessao expirada tem de ser descartada"


def test_numero_de_sessoes_e_limitado():
    boot = Bootstrap()
    sids = [_sessao(boot) for _ in range(boot.MAX_SESSOES + 2)]

    assert len(boot.sessoes) == boot.MAX_SESSOES
    assert boot.sessao_valida(sids[0]) is False, "a mais antiga cai primeiro"
    assert boot.sessao_valida(sids[-1]) is True


def test_duas_threads_nao_trocam_o_mesmo_nonce():
    boot = Bootstrap()
    boot.novo_nonce()
    resultados = []
    barreira = threading.Barrier(2)

    def tentar():
        barreira.wait()
        resultados.append(boot.trocar(boot.nonce, "127.0.0.1"))

    threads = [threading.Thread(target=tentar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len([r for r in resultados if r]) == 1
    assert len(boot.sessoes) == 1
