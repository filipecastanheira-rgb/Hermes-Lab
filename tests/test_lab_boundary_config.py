"""The lab allowlist must survive malformed files and must never be mutated by accident."""
import json

import pytest

from hermes.core import lab_boundary as lb


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    cfg = tmp_path / "lab_allowed.json"
    monkeypatch.setattr(lb, "CONFIG_PATH", str(cfg))
    monkeypatch.setattr(lb, "REDES_PERMITIDAS_DEFAULT", ["127.0.0.0/8"])
    return cfg


def test_adding_a_network_does_not_change_the_built_in_default(isolated):
    lb.adicionar_rede_permitida("10.0.0.0/8")
    isolated.unlink()

    assert lb.alvo_permitido("10.1.2.3") is False
    assert lb.REDES_PERMITIDAS_DEFAULT == ["127.0.0.0/8"]


def test_default_list_is_never_handed_out_by_reference(isolated):
    assert lb._carregar_redes() is not lb.REDES_PERMITIDAS_DEFAULT


BAD_FILES = [
    "[]",
    "[1, 2]",
    '"text"',
    "null",
    "5",
    '{"redes_permitidas": null}',
    '{"redes_permitidas": 5}',
    '{"redes_permitidas": "10.0.0.0/8"}',
    '{"outra_chave": 1}',
]


@pytest.mark.parametrize("conteudo", BAD_FILES)
def test_invalid_structure_falls_back_to_loopback_only(isolated, conteudo):
    isolated.write_text(conteudo)

    assert lb.alvo_permitido("127.0.0.1") is True
    assert lb.alvo_permitido("10.0.0.1") is False


def test_non_string_entries_are_ignored(isolated):
    isolated.write_text(json.dumps({"redes_permitidas": [5, "192.168.100.0/24"]}))

    assert lb.alvo_permitido("0.0.0.5") is False
    assert lb.alvo_permitido("192.168.100.7") is True


def test_empty_list_authorizes_nothing(isolated):
    isolated.write_text('{"redes_permitidas": []}')

    assert lb.alvo_permitido("127.0.0.1") is False


def test_valid_file_replaces_the_default(isolated):
    isolated.write_text('{"redes_permitidas": ["192.168.100.0/24"]}')

    assert lb.alvo_permitido("192.168.100.5") is True
    assert lb.alvo_permitido("127.0.0.1") is False


def test_missing_file_allows_only_loopback(isolated):
    assert lb.alvo_permitido("127.0.0.1") is True
    assert lb.alvo_permitido("192.168.1.1") is False
