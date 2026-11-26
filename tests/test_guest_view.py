"""The guest view: read-only, loopback or tunnel only, and it shows only what the page needs."""
import json

import pytest

from hermes.purple.guest_view import (
    GuestView, arrancar_se_configurado, carregar_config, endereco_bind_convidado,
)

BIND, PORTA = "127.0.0.1", 5001

RICH = {
    "estado": "ok",
    "metricas": {
        "contadores": {
            "heartbeat_purple": 7, "healthcheck_falha": 1,
            "tokens_emitidos": 3, "ultimo_ip": "203.0.113.9",
        },
        "extra": "x",
    },
    "alertas_recentes": [
        {"timestamp": 1700000000, "origem": "nmap", "descricao": "Open port 22",
         "contexto": {"src_ip": "198.51.100.7"}, "token_ref": "abc"},
        {"timestamp": 1700000001,
         "evento": {"origem": "suricata", "assinatura": "ET SCAN", "payload": "secret"}},
    ],
    "config": {"intervalo_heartbeat": 1},
    "historico": ["a", "b"],
    "ultimo_relatorio": "private report",
}


class FakeLogger:
    def __init__(self):
        self.info_lines = []
        self.error_lines = []

    def info(self, mensagem):
        self.info_lines.append(mensagem)

    def error(self, mensagem):
        self.error_lines.append(mensagem)


class FakeDashboard:
    def __init__(self, dados=None):
        self.dados = dados if dados is not None else RICH

    def gerar_dashboard(self):
        return self.dados


@pytest.fixture(autouse=True)
def fixed_ai_state(monkeypatch):
    monkeypatch.setattr("hermes.core.hermes_intelligence.obter_estado_ia", lambda: "cloud")


def _view(dashboard=None, bind=BIND, porta=PORTA):
    logger = FakeLogger()
    return GuestView(dashboard or FakeDashboard(), logger, bind, porta), logger


def _get(view, path="/", host=None, method="GET"):
    host = host if host is not None else f"{view.bind}:{view.porta}"
    return view.app.test_client().open(path, method=method, headers={"Host": host})


def _config(tmp_path, conteudo):
    p = tmp_path / "guest_config.json"
    p.write_text(conteudo)
    return p


# --- where it may listen ---------------------------------------------------

@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.5", "::1", "10.99.0.1", "10.99.0.254"])
def test_bind_accepts_loopback_and_tunnel(host):
    assert endereco_bind_convidado(host) == host


@pytest.mark.parametrize("host", [
    "0.0.0.0", "::", "192.168.1.10", "10.99.1.1", "10.0.0.1", "8.8.8.8",
    "localhost", "", "abc", None, "127.0.0.1/8",
])
def test_bind_refuses_everything_else(host):
    with pytest.raises(ValueError):
        endereco_bind_convidado(host)


def test_view_refuses_to_be_built_on_an_exposed_address():
    with pytest.raises(ValueError):
        GuestView(FakeDashboard(), FakeLogger(), "0.0.0.0")


# --- when it starts --------------------------------------------------------

def test_config_missing_means_disabled(tmp_path):
    assert carregar_config(tmp_path / "nao_existe.json") is None


@pytest.mark.parametrize("conteudo", [
    '{"ativo": false, "bind": "127.0.0.1"}', '{"bind": "127.0.0.1"}', '{"ativo": "true"}',
    '{"ativo": 1}', '{"ativo": null}', '[]', '"x"', 'null',
])
def test_config_that_does_not_say_ativo_true_means_disabled(tmp_path, conteudo):
    assert carregar_config(_config(tmp_path, conteudo)) is None


def test_config_with_ativo_true_is_returned(tmp_path):
    cfg = carregar_config(_config(tmp_path, '{"ativo": true, "bind": "127.0.0.1", "porta": 5001}'))
    assert cfg == {"ativo": True, "bind": "127.0.0.1", "porta": 5001}


def test_config_that_is_not_valid_json_is_not_silently_ignored(tmp_path):
    with pytest.raises(ValueError):
        carregar_config(_config(tmp_path, "{not json"))


@pytest.fixture
def no_server(monkeypatch):
    iniciadas = []
    monkeypatch.setattr(GuestView, "iniciar", lambda self: iniciadas.append((self.bind, self.porta)))
    return iniciadas


def test_start_is_skipped_without_config(tmp_path, no_server):
    logger = FakeLogger()

    assert arrancar_se_configurado(FakeDashboard(), logger, tmp_path / "none.json") is None
    assert no_server == []
    assert any("disabled" in m for m in logger.info_lines)


def test_start_runs_the_view_in_its_own_thread_when_enabled(tmp_path, no_server):
    cfg = _config(tmp_path, '{"ativo": true, "bind": "127.0.0.1", "porta": 5999}')

    thread = arrancar_se_configurado(FakeDashboard(), FakeLogger(), cfg)
    thread.join(timeout=2)

    assert thread.name == "guest-view"
    assert no_server == [("127.0.0.1", 5999)]


@pytest.mark.parametrize("bind", ["0.0.0.0", "192.168.1.10", None])
def test_start_refuses_an_exposed_bind(tmp_path, no_server, bind):
    cfg = _config(tmp_path, json.dumps({"ativo": True, "bind": bind}))

    with pytest.raises(ValueError):
        arrancar_se_configurado(FakeDashboard(), FakeLogger(), cfg)

    assert no_server == []


# --- who may ask, and how --------------------------------------------------

@pytest.mark.parametrize("metodo", ["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
@pytest.mark.parametrize("path", ["/", "/data"])
def test_only_get_is_answered(metodo, path):
    view, _ = _view()

    r = _get(view, path, method=metodo)

    assert r.status_code == 405
    assert r.headers["Allow"] == "GET"


@pytest.mark.parametrize("host", [
    "evil.example", "localhost", "127.0.0.1:5002", "127.0.0.1:5001.evil.com",
    "127.0.0.1.nip.io", "10.99.0.1:5001",
])
def test_wrong_host_is_refused_with_400(host):
    view, _ = _view()

    assert _get(view, "/", host=host).status_code == 400


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:5001"])
def test_host_matching_the_bind_is_accepted(host):
    view, _ = _view()

    assert _get(view, "/data", host=host).status_code == 200


def test_ipv6_loopback_host_in_browser_form_is_accepted():
    view, _ = _view(bind="::1")

    assert _get(view, "/data", host="[::1]:5001").status_code == 200


# --- what it shows ---------------------------------------------------------

def test_data_has_exactly_the_fields_the_page_shows():
    d = _get(_view()[0], "/data").get_json()

    assert set(d) == {"estado", "contadores", "alertas_recentes", "ai"}
    assert d["contadores"] == {"heartbeat_purple": 7, "healthcheck_falha": 1}
    assert d["estado"] == "ok"
    assert d["ai"] == "cloud"


def test_alerts_are_reduced_to_three_fields():
    d = _get(_view()[0], "/data").get_json()

    assert d["alertas_recentes"] == [
        {"timestamp": 1700000000, "origem": "nmap", "descricao": "Open port 22"},
        {"timestamp": 1700000001, "origem": "suricata", "descricao": "ET SCAN"},
    ]


@pytest.mark.parametrize("segredo", [
    "private report", "203.0.113.9", "198.51.100.7", "tokens_emitidos",
    "secret", "abc", "intervalo_heartbeat", "historico",
])
def test_nothing_outside_the_page_fields_leaves_the_server(segredo):
    corpo = _get(_view()[0], "/data").get_data(as_text=True)

    assert segredo not in corpo


@pytest.mark.parametrize("bruto", [
    {},
    {"metricas": "x", "alertas_recentes": "y"},
    {"metricas": {"contadores": [1]}, "alertas_recentes": [None, 5, "x", []]},
])
def test_malformed_dashboard_data_does_not_crash_the_data_route(bruto):
    r = _get(_view(FakeDashboard(bruto))[0], "/data")

    assert r.status_code == 200
    d = r.get_json()
    assert d["contadores"] == {"heartbeat_purple": 0, "healthcheck_falha": 0}
    assert d["estado"] == "?"


def test_counters_that_are_not_numbers_become_zero():
    bruto = {"metricas": {"contadores": {"heartbeat_purple": True, "healthcheck_falha": "9"}}}

    d = _get(_view(FakeDashboard(bruto))[0], "/data").get_json()

    assert d["contadores"] == {"heartbeat_purple": 0, "healthcheck_falha": 0}


@pytest.mark.parametrize("valor,esperado", [
    ("local", "local"), ("none", "none"), ("cloud", "cloud"),
    ("http://evil", "unknown"), (None, "unknown"), (5, "unknown"),
])
def test_ai_state_is_one_of_the_known_values(monkeypatch, valor, esperado):
    monkeypatch.setattr("hermes.core.hermes_intelligence.obter_estado_ia", lambda: valor)

    assert _get(_view()[0], "/data").get_json()["ai"] == esperado


def test_ai_state_failure_is_logged_and_shown_as_unknown(monkeypatch):
    def falha():
        raise RuntimeError("down")

    monkeypatch.setattr("hermes.core.hermes_intelligence.obter_estado_ia", falha)
    view, logger = _view()

    assert _get(view, "/data").get_json()["ai"] == "unknown"
    assert any("could not read AI state" in m for m in logger.error_lines)


# --- headers and page ------------------------------------------------------

@pytest.mark.parametrize("path", ["/", "/data"])
def test_every_response_carries_the_protective_headers(path):
    r = _get(_view()[0], path)

    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in r.headers["Cache-Control"]
    assert r.headers["Referrer-Policy"] == "no-referrer"


def test_refused_responses_carry_the_protective_headers():
    view, _ = _view()

    for r in (_get(view, "/", host="evil.example"), _get(view, "/", method="POST")):
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["Referrer-Policy"] == "no-referrer"


def test_page_has_a_strict_csp_with_a_nonce_that_is_in_the_page():
    r = _get(_view()[0], "/")
    corpo = r.get_data(as_text=True)
    csp = r.headers["Content-Security-Policy"]

    assert r.status_code == 200
    for diretiva in ("default-src 'none'", "connect-src 'self'", "base-uri 'none'",
                     "form-action 'none'", "frame-ancestors 'none'"):
        assert diretiva in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    nonce = csp.split("script-src 'nonce-")[1].split("'")[0]
    assert nonce and nonce in corpo
    assert "__NONCE__" not in corpo


def test_nonce_changes_on_every_request():
    view, _ = _view()

    assert _get(view, "/").headers["Content-Security-Policy"] != \
        _get(view, "/").headers["Content-Security-Policy"]


def test_page_does_not_build_html_from_data():
    corpo = _get(_view()[0], "/").get_data(as_text=True)

    for perigoso in ("innerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert perigoso not in corpo


# --- the log ---------------------------------------------------------------

def test_every_request_is_logged_accepted_or_refused():
    view, logger = _view()

    _get(view, "/data")
    _get(view, "/data", host="evil.example")
    _get(view, "/data", method="POST")

    linhas = [m for m in logger.info_lines if m.startswith("Guest request")]
    assert len(linhas) == 3
    assert "-> 200" in linhas[0] and "-> 400" in linhas[1] and "-> 405" in linhas[2]


def test_log_lines_do_not_grow_with_the_request():
    view, logger = _view()

    _get(view, "/" + "a" * 5000, host="b" * 5000)

    linha = [m for m in logger.info_lines if m.startswith("Guest request")][0]
    assert len(linha) < 400


def test_ipv6_host_without_brackets_is_refused():
    """'::1:5001' is another IPv6 address, not host ::1 on port 5001, and no browser sends it."""
    view, _ = _view(bind="::1")

    assert _get(view, "/data", host="::1:5001").status_code == 400
