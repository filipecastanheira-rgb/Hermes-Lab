"""A target may be inside the lab and still too large to scan: the size limit."""
import pytest

from hermes.core import lab_boundary as lb
import hermes.tools.nmap.nmap_reader as nmap_reader
import hermes.tools.openvas.openvas_reader as openvas_reader


@pytest.fixture(autouse=True)
def loopback_only(tmp_path, monkeypatch):
    monkeypatch.setattr(lb, "CONFIG_PATH", str(tmp_path / "none.json"))


@pytest.mark.parametrize("alvo", ["127.0.0.1", "192.168.100.0/24", "::1"])
def test_small_targets_are_within_the_limit(alvo):
    assert lb.alvo_dentro_do_limite(alvo) is True


@pytest.mark.parametrize("alvo", [
    "192.168.0.0/23", "127.0.0.0/8", "10.0.0.0/8", "0.0.0.0/0", "2001:db8::/64", "::/0",
])
def test_large_targets_are_over_the_limit(alvo):
    assert lb.alvo_dentro_do_limite(alvo) is False


@pytest.mark.parametrize("alvo", ["abc", "", "300.1.1.1"])
def test_invalid_targets_are_refused(alvo):
    assert lb.alvo_dentro_do_limite(alvo) is False


def test_limit_can_be_given_explicitly():
    assert lb.alvo_dentro_do_limite("192.168.0.0/23", max_enderecos=512) is True


def _fake_nmap(monkeypatch):
    chamadas = []

    def fake_run(args, **kwargs):
        chamadas.append(args)
        raise FileNotFoundError

    monkeypatch.setattr(nmap_reader.subprocess, "run", fake_run)
    return chamadas


@pytest.mark.parametrize("alvo", ["127.0.0.0/8", "127.0.0.0/16", "127.0.0.0/23"])
def test_nmap_does_not_run_against_a_target_over_the_limit(monkeypatch, alvo):
    chamadas = _fake_nmap(monkeypatch)

    assert nmap_reader._correr_scan(alvo) == []
    assert chamadas == []


@pytest.mark.parametrize("alvo", ["127.0.0.1", "127.0.0.0/24"])
def test_nmap_still_runs_against_a_small_target(monkeypatch, alvo):
    chamadas = _fake_nmap(monkeypatch)

    nmap_reader._correr_scan(alvo)

    assert len(chamadas) == 1


def _fake_openvas(monkeypatch):
    chamadas = []

    def fake_target(alvo):
        chamadas.append(alvo)
        return None

    monkeypatch.setattr(openvas_reader, "_obter_ou_criar_target", fake_target)
    return chamadas


@pytest.mark.parametrize("alvo", ["127.0.0.0/8", "127.0.0.0/16", "127.0.0.0/23"])
def test_openvas_does_not_start_against_a_target_over_the_limit(monkeypatch, alvo):
    chamadas = _fake_openvas(monkeypatch)

    assert openvas_reader.ler_uma_vez(alvo) == []
    assert chamadas == []


@pytest.mark.parametrize("alvo", ["127.0.0.1", "127.0.0.0/24"])
def test_openvas_still_starts_against_a_small_target(monkeypatch, alvo):
    chamadas = _fake_openvas(monkeypatch)

    openvas_reader.ler_uma_vez(alvo)

    assert chamadas == [alvo]
