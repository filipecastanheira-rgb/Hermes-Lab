"""
guest_view.py
Vista de convidado, so de leitura, do dashboard PURPLE.

Servidor Flask proprio, separado do purple_api: nao partilha rotas, token
nem sessao com ele. Expoe apenas duas rotas GET:
  /      pagina HTML (so leitura, sem login e sem execucao de tools)
  /data  JSON com os campos que a pagina mostra, e mais nenhum

Invariantes:
- so responde a GET;
- bind apenas em loopback ou na rede do tunel, nunca em 0.0.0.0;
- o cabecalho Host tem de coincidir com o endereco e porta de bind;
- cada pedido, aceite ou recusado, fica registado;
- so arranca se config/guest_config.json existir com "ativo": true.
"""

import ipaddress
import json
import secrets
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request

CONFIG_CAMINHO = Path("config/guest_config.json")
REDE_TUNEL = ipaddress.ip_network("10.99.0.0/24")
PORTA_DEFEITO = 5001
CONTADORES_VISIVEIS = ("heartbeat_purple", "healthcheck_falha")
ESTADOS_IA = {"cloud", "local", "none", "unknown"}


def endereco_bind_convidado(host):
    """Devolve o endereco de bind, recusando tudo o que nao seja loopback
    ou rede do tunel. Falha com ValueError em vez de arrancar exposto."""
    try:
        ip = ipaddress.ip_address(str(host))
    except ValueError:
        raise ValueError(f"Guest bind refused: {host!r} is not an IP address.")
    if ip.is_unspecified or not (ip.is_loopback or ip in REDE_TUNEL):
        raise ValueError(
            f"Guest bind refused: {host!r}. The guest view can only listen "
            f"on loopback or inside {REDE_TUNEL}."
        )
    return str(ip)


def carregar_config(caminho=CONFIG_CAMINHO):
    """Devolve a configuracao se existir e pedir o arranque; senao None."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return None
    with caminho.open(encoding="utf-8") as f:
        config = json.load(f)
    if not isinstance(config, dict) or config.get("ativo") is not True:
        return None
    return config


def _numero(valor):
    return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else 0


def _texto(valor, defeito=""):
    return valor if isinstance(valor, str) and valor else defeito


_PAGINA_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Hermes — Guest view</title>
<style nonce="__NONCE__">
  body { font-family: system-ui, sans-serif; background: #0f1117; color: #e6e6e6; margin: 0; padding: 24px; }
  h1 { color: #7ee787; font-size: 1.4rem; margin-bottom: 4px; }
  h2.sec { color: #8b949e; font-size: 0.9rem; }
  .sub { color: #8b949e; font-size: 0.85rem; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card h2 { font-size: 0.8rem; text-transform: uppercase; color: #8b949e; margin: 0 0 8px 0; }
  .card .valor { font-size: 1.8rem; font-weight: 600; color: #7ee787; }
  table { width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }
  th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #30363d; font-size: 0.85rem; }
  th { color: #8b949e; text-transform: uppercase; font-size: 0.7rem; }
  .vazio { color: #8b949e; padding: 16px; text-align: center; }
  .status { color: #58a6ff; font-size: 0.75rem; }
  #indicador-ia { font-size: 0.85rem; color: #8b949e; margin-bottom: 16px; }
</style>
</head>
<body>
<h1>Hermes — PURPLE Dashboard (read-only)</h1>
<div class="sub">Refreshes automatically every 5s · <span id="ultima-atualizacao" class="status">loading...</span></div>

<div class="grid" id="cartoes"></div>
<div id="indicador-ia">AI: not checked yet</div>

<h2 class="sec">Events by source</h2>
<div class="grid" id="origens"></div>

<h2 class="sec">Recent alerts</h2>
<table id="tabela-alertas">
  <thead><tr><th>Time</th><th>Source</th><th>Description</th></tr></thead>
  <tbody><tr><td colspan="3" class="vazio">loading...</td></tr></tbody>
</table>

<script nonce="__NONCE__">
// Nenhum HTML e construido a partir de dados: tudo entra por textContent.
const $ = (id) => document.getElementById(id);

function cartao(titulo, valor) {
  const d = document.createElement("div");
  d.className = "card";
  const h = document.createElement("h2");
  h.textContent = titulo;
  const v = document.createElement("div");
  v.className = "valor";
  v.textContent = valor;
  d.append(h, v);
  return d;
}

async function atualizar() {
  try {
    const r = await fetch("/data", {cache: "no-store"});
    if (!r.ok) {
      $("ultima-atualizacao").textContent = "update error: HTTP " + r.status;
      return;
    }
    const d = await r.json();
    const contadores = d.contadores || {};
    const alertas = d.alertas_recentes || [];

    $("cartoes").replaceChildren(
      cartao("Status", d.estado || "?"),
      cartao("Heartbeats PURPLE", contadores.heartbeat_purple || 0),
      cartao("Health-check failures (this run)", contadores.healthcheck_falha || 0),
      cartao("Operation", "manual")
    );

    const contagem = new Map();
    alertas.forEach((a) => {
      const origem = a.origem || "unknown";
      contagem.set(origem, (contagem.get(origem) || 0) + 1);
    });
    const origens = [...contagem.entries()].map(([o, n]) => cartao(o, n));
    $("origens").replaceChildren(...(origens.length ? origens : [cartao("No data yet", "-")]));

    const tbody = $("tabela-alertas").querySelector("tbody");
    if (!alertas.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 3;
      td.className = "vazio";
      td.textContent = "No alerts yet.";
      tr.append(td);
      tbody.replaceChildren(tr);
    } else {
      tbody.replaceChildren(
        ...alertas.slice(-20).reverse().map((a) => {
          const tr = document.createElement("tr");
          const quando = document.createElement("td");
          quando.textContent = new Date((a.timestamp || 0) * 1000).toLocaleTimeString();
          const origem = document.createElement("td");
          origem.textContent = a.origem || "-";
          const desc = document.createElement("td");
          desc.textContent = a.descricao || "-";
          tr.append(quando, origem, desc);
          return tr;
        })
      );
    }

    const estadosIA = {cloud: "AI: Cloud AI", local: "AI: Local AI", none: "AI: none available", unknown: "AI: not checked yet"};
    $("indicador-ia").textContent = estadosIA[d.ai] || "AI: not checked yet";
    $("ultima-atualizacao").textContent = "last update: " + new Date().toLocaleTimeString();
  } catch (e) {
    $("ultima-atualizacao").textContent = "update error: " + e;
  }
}

atualizar();
setInterval(atualizar, 5000);
</script>
</body>
</html>
"""


class GuestView:
    def __init__(self, dashboard, logger, bind, porta=PORTA_DEFEITO):
        self.dashboard = dashboard
        self.logger = logger
        self.bind = endereco_bind_convidado(bind)
        self.porta = int(porta)
        self.hosts_permitidos = {self.bind, f"{self.bind}:{self.porta}"}
        self.app = Flask(__name__, static_folder=None)
        self._registar_rotas()

    def _dados(self):
        """Reduz o dashboard aos campos que a pagina mostra. Tudo o resto
        (config, historico, ultimo relatorio) fica de fora por construcao."""
        bruto = self.dashboard.gerar_dashboard()

        metricas = bruto.get("metricas")
        contadores_brutos = metricas.get("contadores") if isinstance(metricas, dict) else None
        if not isinstance(contadores_brutos, dict):
            contadores_brutos = {}
        contadores = {k: _numero(contadores_brutos.get(k)) for k in CONTADORES_VISIVEIS}

        alertas_brutos = bruto.get("alertas_recentes")
        if not isinstance(alertas_brutos, list):
            alertas_brutos = []
        alertas = []
        for a in alertas_brutos:
            a = a if isinstance(a, dict) else {}
            evento = a.get("evento") if isinstance(a.get("evento"), dict) else {}
            alertas.append({
                "timestamp": _numero(a.get("timestamp")),
                "origem": _texto(a.get("origem")) or _texto(evento.get("origem")),
                "descricao": _texto(a.get("descricao")) or _texto(evento.get("assinatura"), "-"),
            })

        try:
            from hermes.core.hermes_intelligence import obter_estado_ia
            ai = obter_estado_ia()
        except Exception as e:
            self.logger.error(f"Guest view: could not read AI state: {e}")
            ai = "unknown"
        if ai not in ESTADOS_IA:
            ai = "unknown"

        return {
            "estado": _texto(bruto.get("estado"), "?"),
            "contadores": contadores,
            "alertas_recentes": alertas,
            "ai": ai,
        }

    def _registar_rotas(self):
        app = self.app

        @app.before_request
        def _validar():
            if request.method != "GET":
                return Response("Method not allowed.", 405, {"Allow": "GET"})
            host = request.headers.get("Host", "").lower()
            if host not in self.hosts_permitidos:
                return Response("Invalid host.", 400)
            return None

        @app.after_request
        def _registar_e_proteger(resposta):
            resposta.headers["X-Content-Type-Options"] = "nosniff"
            resposta.headers["Cache-Control"] = "no-store"
            resposta.headers["Referrer-Policy"] = "no-referrer"
            self.logger.info(
                f"Guest request: {request.remote_addr} {request.method} "
                f"{request.path[:100]!r} host={request.headers.get('Host', '')[:100]!r} "
                f"-> {resposta.status_code}"
            )
            return resposta

        @app.route("/", methods=["GET"])
        def pagina():
            nonce = secrets.token_urlsafe(16)
            html = _PAGINA_HTML.replace("__NONCE__", nonce)
            resposta = Response(html, mimetype="text/html")
            resposta.headers["Content-Security-Policy"] = (
                f"default-src 'none'; script-src 'nonce-{nonce}'; "
                f"style-src 'nonce-{nonce}'; connect-src 'self'; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            )
            return resposta

        @app.route("/data", methods=["GET"])
        def dados():
            return jsonify(self._dados())

    def iniciar(self):
        self.logger.info(f"Guest view starting on {self.bind}:{self.porta}.")
        self.app.run(host=self.bind, port=self.porta, use_reloader=False, threaded=True)


def arrancar_se_configurado(dashboard, logger, caminho=CONFIG_CAMINHO):
    """Arranca a vista de convidado em thread propria, so se a configuracao
    local o pedir. Devolve a thread, ou None se ficou desligada."""
    config = carregar_config(caminho)
    if config is None:
        logger.info("Guest view disabled (no local config).")
        return None
    vista = GuestView(
        dashboard,
        logger,
        config.get("bind"),
        config.get("porta", PORTA_DEFEITO),
    )
    thread = threading.Thread(target=vista.iniciar, daemon=True, name="guest-view")
    thread.start()
    return thread
