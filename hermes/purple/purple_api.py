from flask import Flask, request, jsonify, Response

from hermes.tools.agregador_ferramentas import ler_uma_vez_todas
from hermes.core.lab_boundary import alvo_permitido
from functools import wraps


class PurpleAPI:
    """
    API interna do modo PURPLE.
    Autenticação + auditoria + rate limiting + cache + compressão + webhooks + dashboard.

    Corrigido: o ficheiro original cortava a meio da rota
    /token/regenerar (erro de sintaxe — string por fechar). Esta versão
    está completa e foi testada a instanciar e a arrancar.
    """

    def __init__(self, commands, config, metrics, alerts, logger,
                 auth, api_logger, ratelimit, cache, compression, webhooks, dashboard):

        self.commands = commands
        self.config = config
        self.metrics = metrics
        self.alerts = alerts
        self.logger = logger
        self.auth = auth
        self.api_logger = api_logger
        self.ratelimit = ratelimit
        self.cache = cache
        self.compression = compression
        self.webhooks = webhooks
        self.dashboard = dashboard

        self.app = Flask("HermesPurpleAPI")
        self._definir_rotas()

    def _require_token(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            token = request.headers.get("X-Hermes-Token") or request.args.get("token")
            ip = request.remote_addr
            endpoint = request.path

            self.api_logger.log_chamada(
                endpoint=endpoint,
                metodo=request.method,
                token=token,
                payload=request.json if request.is_json else {},
            )

            if not self.ratelimit.verificar_ip(ip):
                self.api_logger.log_acesso_negado(endpoint, f"Rate limit IP excedido ({ip})")
                return jsonify({"erro": "Rate limit excedido para este IP"}), 429

            if token and not self.ratelimit.verificar_token(token):
                self.api_logger.log_acesso_negado(endpoint, f"Rate limit token excedido ({token})")
                return jsonify({"erro": "Rate limit excedido para este token"}), 429

            if not token or not self.auth.validar(token):
                self.api_logger.log_erro_autenticacao(endpoint, token)
                return jsonify({"erro": "Token inválido ou ausente"}), 403

            return func(*args, **kwargs)
        return wrapper

    def _responder(self, endpoint, dados, webhook_evento=None):
        self.api_logger.log_resposta(endpoint, dados)

        if webhook_evento:
            try:
                self.webhooks.enviar(webhook_evento)
            except Exception:
                self.logger.warn(f"Falha ao enviar webhook da API ({endpoint}).")

        aceita_gzip = "gzip" in request.headers.get("Accept-Encoding", "").lower()

        if aceita_gzip:
            comprimido, ok = self.compression.comprimir(dados)
            if ok:
                return Response(
                    comprimido,
                    status=200,
                    headers={"Content-Encoding": "gzip", "Content-Type": "application/json"},
                )

        return jsonify(dados)

    def _definir_rotas(self):

        @self.app.route("/status", methods=["GET"])
        @self._require_token
        def status():
            cache_key = "status"
            resposta_cache = self.cache.obter(cache_key)
            if resposta_cache:
                return self._responder("/status", resposta_cache)

            stats = self.metrics.obter_estatisticas()
            resposta = {
                "status": "Hermes PURPLE ativo",
                "config": self.config.config,
                "metricas": stats,
            }
            self.cache.guardar(cache_key, resposta)

            return self._responder(
                "/status", resposta,
                webhook_evento={"tipo": "status", "descricao": "Consulta de estado via API PURPLE", "metricas": stats},
            )

        @self.app.route("/comando", methods=["POST"])
        @self._require_token
        def comando():
            dados = request.json or {}
            cmd = dados.get("comando")
            valor = dados.get("valor")

            resultado = self.commands.executar(cmd, valor)
            resposta = {"resultado": resultado}

            return self._responder(
                "/comando", resposta,
                webhook_evento={"tipo": "comando", "descricao": "Comando executado via API PURPLE",
                                "comando": cmd, "valor": valor, "resultado": resultado},
            )

        @self.app.route("/alerta", methods=["POST"])
        @self._require_token
        def alerta_manual():
            dados = request.json or {}
            descricao = dados.get("descricao", "Alerta manual via API")
            severidade = dados.get("severidade", "ALTO")
            contexto = dados.get("contexto", {})

            alerta = self.alerts.emitir_alerta(
                severidade=severidade, origem="API", descricao=descricao, contexto=contexto,
            )

            return self._responder(
                "/alerta", alerta,
                webhook_evento={"tipo": "alerta", "descricao": "Alerta manual emitido via API PURPLE", "alerta": alerta},
            )

        @self.app.route("/config", methods=["POST"])
        @self._require_token
        def atualizar_config():
            dados = request.json or {}
            chave = dados.get("chave")
            valor = dados.get("valor")

            if chave not in self.config.config:
                self.api_logger.log_acesso_negado("/config", "Chave inválida")
                return jsonify({"erro": "Chave de configuração inválida"}), 400

            self.config.atualizar(chave, valor)
            resposta = {"resultado": f"Configuração '{chave}' atualizada para {valor}"}
            self.cache.guardar("config", resposta)

            return self._responder(
                "/config", resposta,
                webhook_evento={"tipo": "config", "descricao": "Configuração PURPLE alterada via API", "chave": chave, "valor": valor},
            )

        @self.app.route("/token/regenerar", methods=["POST"])
        @self._require_token
        def regenerar_token():
            dados = request.json or {}
            base = dados.get("base", "hermes-default")

            novo_token = self.auth.atualizar_token(base)
            self.api_logger.log_token_regenerado(novo_token)

            resposta = {"novo_token": novo_token}

            return self._responder(
                "/token/regenerar", resposta,
                webhook_evento={"tipo": "token", "descricao": "Token regenerado via API PURPLE"},
            )

        @self.app.route("/dashboard", methods=["GET"])
        @self._require_token
        def dashboard():
            if self.dashboard is None:
                return jsonify({"erro": "Dashboard não está configurado."}), 501

            dados = self.dashboard.gerar_dashboard()
            return self._responder("/dashboard", dados)

        @self.app.route("/dashboard/view", methods=["GET"])
        @self._require_token
        def dashboard_view():
            if self.dashboard is None:
                return "<h1>Dashboard não está configurado.</h1>", 501

            token = request.args.get("token", "")
            return Response(_DASHBOARD_HTML.replace("__TOKEN__", token), mimetype="text/html")

        @self.app.route("/run_tool", methods=["POST"])
        @self._require_token
        def run_tool():
            """
            Runs one tool against a target, on demand, from the
            dashboard form. Always gated by lab_boundary — a
            blocked target is logged as a security alert and refused,
            never silently ignored.
            """
            dados = request.json or {}
            tool = dados.get("tool", "").strip()
            target = dados.get("target", "").strip()

            if not tool or not target:
                return jsonify({"error": "Both 'tool' and 'target' are required."}), 400

            if not alvo_permitido(target):
                alerta = self.alerts.emitir_alerta(
                    severidade="SECURITY",
                    origem="lab_boundary",
                    descricao=f"Blocked out-of-lab target attempt: {target} (tool={tool})",
                    contexto={"tool": tool, "target": target},
                )
                return jsonify({
                    "error": f"Target '{target}' is outside the authorized lab boundary. Attempt logged.",
                }), 403

            eventos = ler_uma_vez_todas({tool: target})

            for evento in eventos:
                self.alerts.emitir_alerta(
                    severidade=str(evento.get("severidade") or "INFO"),
                    origem=evento.get("origem", tool),
                    descricao=evento.get("assinatura", "Event found"),
                    contexto=evento,
                )

            return self._responder(
                "/run_tool",
                {"tool": tool, "target": target, "events_found": len(eventos), "events": eventos},
            )

    def iniciar(self, porta=5000):
        """
        Arranca o servidor Flask. Corre em thread separada, arrancada
        pelo purple_runner.
        """
        self.logger.info(f"API PURPLE a arrancar na porta {porta}.")
        self.app.run(host="0.0.0.0", port=porta, use_reloader=False)


_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="utf-8">
<title>Hermes — Dashboard</title>
<style>
  body { font-family: system-ui, sans-serif; background: #0f1117; color: #e6e6e6; margin: 0; padding: 24px; }
  h1 { color: #7ee787; font-size: 1.4rem; margin-bottom: 4px; }
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
</style>
</head>
<body>
<h1>Hermes — Dashboard PURPLE</h1>
<div class="sub">Atualiza automaticamente a cada 5s · <span id="ultima-atualizacao" class="status">a carregar...</span></div>

<div class="grid" id="cartoes"></div>

<h2 style="color:#8b949e; font-size:0.9rem;">Run a tool</h2>
<div class="card" style="margin-bottom:24px; display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
  <select id="ferramenta" style="background:#0f1117; color:#e6e6e6; border:1px solid #30363d; padding:8px; border-radius:6px;">
    <option value="nmap">nmap</option>
  </select>
  <input id="alvo" type="text" value="127.0.0.1" style="background:#0f1117; color:#e6e6e6; border:1px solid #30363d; padding:8px; border-radius:6px; flex:1; min-width:160px;">
  <button id="btn-correr" style="background:#238636; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer;">Run</button>
  <span id="resultado-correr" style="font-size:0.85rem;"></span>
</div>

<h2 style="color:#8b949e; font-size:0.9rem;">Events by source</h2>
<div class="grid" id="origens" style="margin-bottom:24px;"></div>

<h2 style="color:#8b949e; font-size:0.9rem;">Recent alerts</h2>
<table id="tabela-alertas">
  <thead><tr><th>Hora</th><th>Origem</th><th>Descrição</th></tr></thead>
  <tbody><tr><td colspan="3" class="vazio">a carregar...</td></tr></tbody>
</table>

<script>
const TOKEN = "__TOKEN__";

async function atualizar() {
  try {
    const r = await fetch("/dashboard?token=" + encodeURIComponent(TOKEN));
    const d = await r.json();

    const metricas = d.metricas || {};
    const contadores = metricas.contadores || {};
    const alertas = d.alertas_recentes || [];

    document.getElementById("cartoes").innerHTML = `
      <div class="card"><h2>Status</h2><div class="valor" style="font-size:1.1rem;">${d.estado || "?"}</div></div>
      <div class="card"><h2>Heartbeats PURPLE</h2><div class="valor">${contadores.heartbeat_purple || 0}</div></div>
      <div class="card"><h2>Falhas de health-check</h2><div class="valor">${contadores.healthcheck_falha || 0}</div></div>
      <div class="card"><h2>Modo</h2><div class="valor" style="font-size:1.1rem;">${d.modo || "?"}</div></div>
    `;

    const contagemOrigens = {};
    alertas.forEach(a => {
      const origem = a.origem || a.evento?.origem || "unknown";
      contagemOrigens[origem] = (contagemOrigens[origem] || 0) + 1;
    });
    const origensHtml = Object.keys(contagemOrigens).length
      ? Object.entries(contagemOrigens).map(([origem, n]) => `
          <div class="card"><h2>${origem}</h2><div class="valor">${n}</div></div>
        `).join("")
      : `<div class="card"><h2>No data yet</h2><div class="valor" style="font-size:1rem;">-</div></div>`;
    document.getElementById("origens").innerHTML = origensHtml;

    const corpo = alertas.length
      ? alertas.slice(-20).reverse().map(a => `
          <tr>
            <td>${new Date((a.timestamp||0)*1000).toLocaleTimeString()}</td>
            <td>${(a.origem || a.evento?.origem || "-")}</td>
            <td>${(a.descricao || a.evento?.assinatura || JSON.stringify(a).slice(0,80))}</td>
          </tr>`).join("")
      : `<tr><td colspan="3" class="vazio">Sem alertas ainda.</td></tr>`;

    document.getElementById("tabela-alertas").querySelector("tbody").innerHTML = corpo;
    document.getElementById("ultima-atualizacao").textContent = "última atualização: " + new Date().toLocaleTimeString();
  } catch (e) {
    document.getElementById("ultima-atualizacao").textContent = "erro a atualizar: " + e;
  }
}

document.getElementById("btn-correr").addEventListener("click", async () => {
  const tool = document.getElementById("ferramenta").value;
  const target = document.getElementById("alvo").value;
  const resultadoEl = document.getElementById("resultado-correr");

  resultadoEl.textContent = "Running...";
  resultadoEl.style.color = "#8b949e";

  try {
    const r = await fetch("/run_tool?token=" + encodeURIComponent(TOKEN), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({tool, target}),
    });
    const d = await r.json();

    if (!r.ok) {
      resultadoEl.textContent = d.error || "Blocked.";
      resultadoEl.style.color = "#f85149";
    } else {
      resultadoEl.textContent = `${d.events_found} event(s) found.`;
      resultadoEl.style.color = "#7ee787";
      atualizar();
    }
  } catch (e) {
    resultadoEl.textContent = "Error: " + e;
    resultadoEl.style.color = "#f85149";
  }
});

atualizar();
setInterval(atualizar, 5000);
</script>
</body>
</html>
"""
