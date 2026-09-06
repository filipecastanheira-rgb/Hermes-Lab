"""
tests/test_lab_boundary.py

Testes do único ponto de decisão sobre se um alvo de rede está
dentro do laboratório autorizado (hermes/core/lab_boundary.py).
Cada teste isola a config apontando lab_boundary.CONFIG_PATH para
um ficheiro temporário, nunca tocando no config/lab_allowed.json
real do projeto.
"""
import json
import pytest

from hermes.core import lab_boundary


@pytest.fixture
def custom_config(tmp_path, monkeypatch):
    """Aponta lab_boundary.CONFIG_PATH para um ficheiro de config
    temporário e controlado, com as redes indicadas."""
    def _set(redes_permitidas):
        config_file = tmp_path / "lab_allowed.json"
        config_file.write_text(json.dumps({"redes_permitidas": redes_permitidas}))
        monkeypatch.setattr(lab_boundary, "CONFIG_PATH", str(config_file))
        return config_file
    return _set


def test_ip_dentro_do_range_permitido(custom_config):
    custom_config(["192.168.100.0/24"])
    assert lab_boundary.alvo_permitido("192.168.100.50") is True


def test_ip_fora_do_range_permitido(custom_config):
    custom_config(["192.168.100.0/24"])
    assert lab_boundary.alvo_permitido("10.0.0.5") is False


def test_ip_invalido_falha_seguro(custom_config):
    custom_config(["192.168.100.0/24"])
    assert lab_boundary.alvo_permitido("isto-nao-e-um-ip") is False


def test_ipv6_vs_rede_ipv4_sem_crash(custom_config):
    """Bug real corrigido em 2026-08-19: comparar um alvo IPv6 (ex:
    link-local capturado pelo Zeek) contra uma rede permitida IPv4
    não pode rebentar - deve simplesmente devolver False."""
    custom_config(["192.168.100.0/24"])
    assert lab_boundary.alvo_permitido("fe80::1") is False


def test_sem_ficheiro_config_so_loopback_por_omissao(tmp_path, monkeypatch):
    caminho_inexistente = tmp_path / "nao_existe" / "lab_allowed.json"
    monkeypatch.setattr(lab_boundary, "CONFIG_PATH", str(caminho_inexistente))
    assert lab_boundary.alvo_permitido("127.0.0.1") is True
    assert lab_boundary.alvo_permitido("8.8.8.8") is False


def test_config_json_corrompido_cai_para_omissao(tmp_path, monkeypatch):
    """Ficheiro de config existe mas é ilegível - deve cair para o
    default seguro (só loopback), nunca rebentar nem abrir tudo."""
    config_file = tmp_path / "lab_allowed.json"
    config_file.write_text("{ isto nao e json valido")
    monkeypatch.setattr(lab_boundary, "CONFIG_PATH", str(config_file))
    assert lab_boundary.alvo_permitido("127.0.0.1") is True
    assert lab_boundary.alvo_permitido("8.8.8.8") is False
