import hmac
import secrets
import threading
import time

from flask import Flask, request, jsonify, Response

from hermes.tools.agregador_ferramentas import ler_uma_vez_todas
from hermes.core.lab_boundary import alvo_permitido
from functools import wraps

# Nomes pelos quais a app se pode apresentar. So estes: a API nao foi feita
# para ser acedida por nome nenhum, e o browser de um atacante pode resolver
# um dominio dele para 127.0.0.1 (DNS rebinding) - nesse caso o pedido chega
# a este servidor mas traz esse dominio no cabecalho Host.
HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1"}

# Endereco de bind da API. E uma invariante, nao um parametro: a app nunca
# deve ficar exposta na rede, mesmo que a maquina tenha ligacao a internet.
# Fica aqui como constante e passa por `endereco_bind()` no arranque, para que
# uma alteracao descuidada falhe de imediato em vez de expor o servico.
HOST_BIND = "127.0.0.1"
BINDS_PERMITIDOS = {"127.0.0.1", "::1"}


def endereco_bind(host=None):
    """Devolve o endereco de bind, recusando qualquer coisa que nao seja loopback.

    Aceita apenas enderecos literais de loopback - nao aceita `localhost`,
    porque o nome depende do resolver e do /etc/hosts, enquanto 127.0.0.1 nao
    depende de nada. Falha com ValueError em vez de arrancar exposto: um erro
    no arranque e um incidente visivel, um bind em 0.0.0.0 e um incidente
    silencioso.
    """
    alvo = HOST_BIND if host is None else host
    if alvo not in BINDS_PERMITIDOS:
        raise ValueError(
            f"Bind refused: {alvo!r}. The PURPLE API can only listen on loopback "
            f"({', '.join(sorted(BINDS_PERMITIDOS))}). To expose the service on the network "
            "this invariant would have to be changed on purpose."
        )
    return alvo


def _loopback(ip):
    return (ip or "") in {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


class Bootstrap:
    """Entrada sem token para o dono, a partir da propria maquina.

    O CLI gera um nonce de uso unico, valido TTL segundos, e abre o browser com
    esse nonce no fragmento do URL (#n=...). O fragmento nao e enviado ao
    servidor, nao vai no Referer e nao aparece nos logs de acesso. O JavaScript
    troca-o por uma cookie HttpOnly e apaga-o do URL.

    Nada disto passa por disco: o nonce e as sessoes vivem em memoria e morrem
    com o processo. Reiniciar o servidor obriga a um novo arranque - o que o
    CLI faz de qualquer forma, porque e ele que abre o browser.
    """

    TTL = 60              # validade do nonce de arranque
    SESSAO_TTL = 8 * 3600  # prazo absoluto de uma sessao
    MAX_SESSOES = 10      # sessoes simultaneas; a mais antiga cai primeiro

    def __init__(self):
        self.nonce = None
        self.emitido_em = 0.0
        self.usado = True
        self.sessoes = {}
        self.lock = threading.Lock()

    def novo_nonce(self):
        self.nonce = secrets.token_hex(32)
        self.emitido_em = time.time()
        self.usado = False
        return self.nonce

    def trocar(self, nonce, ip):
        """Devolve um id de sessao novo, ou None.

        O nonce e consumido no primeiro uso, mesmo que a validacao falhe: um
        nonce que sobrevive a uma tentativa errada e um nonce que se pode
        continuar a tentar.
        """
        with self.lock:
            if self.usado or not self.nonce:
                return None
            # Em bytes: compare_digest com str so aceita ASCII e lancaria
            # TypeError antes de o nonce ser consumido.
            igual = hmac.compare_digest(str(nonce or "").encode(), self.nonce.encode())
            expirado = (time.time() - self.emitido_em) > self.TTL
            self.usado = True
            if not igual or expirado or not _loopback(ip):
                return None

            agora = time.time()
            sid = secrets.token_hex(32)
            self.sessoes[sid] = {"criada_em": agora}
            self._podar(agora)
            return sid

    def _podar(self, agora):
        """Descarta sessoes expiradas e limita o total (chamado com o lock)."""
        self.sessoes = {
            k: v for k, v in self.sessoes.items()
            if agora - v["criada_em"] <= self.SESSAO_TTL
        }
        while len(self.sessoes) > self.MAX_SESSOES:
            mais_antiga = min(self.sessoes, key=lambda k: self.sessoes[k]["criada_em"])
            self.sessoes.pop(mais_antiga, None)

    def sessao_valida(self, sid):
        if not sid:
            return False
        with self.lock:
            sessao = self.sessoes.get(sid)
            if sessao is None:
                return False
            if time.time() - sessao["criada_em"] > self.SESSAO_TTL:
                self.sessoes.pop(sid, None)
                return False
            return True

    def revogar(self, sid):
        return self.sessoes.pop(sid, None) is not None


def host_permitido(host_header):
    """True only for a local name, with or without a port.

    The whole name is compared (never a prefix, so `localhost.evil.com` fails)
    and a port, when present, must be digits only. An IPv6 literal has to be
    bracketed, as RFC 3986 requires: `[::1]` or `[::1]:5000`. Any whitespace in
    the value rejects the request instead of being tolerated.
    """
    if not host_header or any(c.isspace() for c in host_header):
        return False

    h = host_header.lower()
    porta = None

    if h.startswith("["):
        if "]" not in h:
            return False
        nome, resto = h[1:].split("]", 1)
        if resto:
            if not resto.startswith(":"):
                return False
            porta = resto[1:]
    elif ":" in h:
        nome, porta = h.rsplit(":", 1)
    else:
        nome = h

    # ASCII digits only: str.isdigit() also accepts Unicode digits such as
    # "\u0665" and "\u00b2". The port must also fit in 16 bits.
    if porta is not None and not (
        porta.isascii() and porta.isdigit() and int(porta) <= 65535
    ):
        return False

    return nome in HOSTS_LOCAIS


class PurpleAPI:
    """
    API interna do camada PURPLE.
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

        self.bootstrap = Bootstrap()
        self.app = Flask("HermesPurpleAPI")

        @self.app.before_request
        def _validar_host():
            """Recusa pedidos cujo Host nao seja um nome local (DNS rebinding).

            Um dominio controlado pelo atacante que resolva para 127.0.0.1 faz
            o browser enviar esse dominio no Host: o pedido chega ao servidor
            a partir da maquina da vitima, com o token dela. Rejeitar Hosts
            desconhecidos fecha essa via sem depender de como o browser trata
            o Same-Origin Policy.
            """
            if not host_permitido(request.headers.get("Host", "")):
                return Response("Host not allowed", status=400, mimetype="text/plain")
            return None

        self._definir_rotas()

    def _recusar_token_na_url(self, endpoint):
        """Devolve uma resposta 403 se o pedido trouxer o token na query string.

        Um token na URL fica no historico do browser, no cabecalho Referer
        enviado a terceiros e nos logs de acesso do servidor - ou seja,
        sobrevive ao pedido. Por isso nao e aceite em rota nenhuma: nem nas
        autenticadas, nem na casca do dashboard (onde seria inerte, mas
        continuaria a ser registado em logs). Devolve None quando o pedido
        nao traz token na URL.
        """
        if request.args.get("token") is None:
            return None

        self.api_logger.log_acesso_negado(
            endpoint,
            "Token recusado na query string (usar o cabecalho X-Hermes-Token)",
        )
        if getattr(self, "alerts", None) is not None:
            self.alerts.emitir_alerta(
                severidade="MEDIO",
                origem="purple_api",
                descricao=f"Request with token in URL refused on {endpoint}",
                contexto={"endpoint": endpoint, "ip": request.remote_addr},
            )
        return jsonify({
            "erro": "Token in the URL is not accepted. Use the X-Hermes-Token header."
        }), 403

    def _require_token(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr
            endpoint = request.path

            recusa = self._recusar_token_na_url(endpoint)
            if recusa is not None:
                return recusa

            token = request.headers.get("X-Hermes-Token")

            # Nota: localmente o cliente e sempre 127.0.0.1, portanto este
            # limite "por IP" funciona na pratica como um limite GLOBAL. E o
            # comportamento pretendido: um servico que so tem um cliente local
            # quer proteger-se de um cliente descontrolado (um bug que dispara
            # pedidos em ciclo), nao de um ataque distribuido. O limite por
            # token e que distingue clientes entre si.
            if not self.ratelimit.verificar_ip(ip):
                self.api_logger.log_acesso_negado(endpoint, f"Rate limit IP excedido ({ip})")
                return jsonify({"erro": "Rate limit exceeded for this IP"}), 429

            if token and not self.ratelimit.verificar_token(token):
                self.api_logger.log_acesso_negado(endpoint, "Rate limit do token excedido")
                return jsonify({"erro": "Rate limit exceeded for this token"}), 429

            sid = request.cookies.get("hermes_session")
            if sid and self.bootstrap.sessao_valida(sid):
                identidade = {"id": "sessao-local", "nome": "local"}
            else:
                identidade = self.auth.validar(token) if token else None
            if identidade is None:
                self.api_logger.log_erro_autenticacao(endpoint, token)
                return jsonify({"erro": "Invalid or missing token"}), 403

            # Uma cookie viaja sozinha em qualquer pedido que o browser faca a
            # este host, por isso um pedido que altera estado tem de provar que
            # veio da propria pagina: o Origin tem de ser o deste servidor.
            if identidade.get("id") == "sessao-local" and request.method not in ("GET", "HEAD", "OPTIONS"):
                esperado = f"http://{request.host}"
                if request.headers.get("Origin") != esperado:
                    self.api_logger.log_acesso_negado(
                        endpoint, "Origem inesperada num pedido autenticado por cookie")
                    if getattr(self, "alerts", None) is not None:
                        self.alerts.emitir_alerta(
                            severidade="MEDIO",
                            origem="purple_api",
                            descricao=f"Request with cookie and mismatched Origin refused on {endpoint}",
                            contexto={"endpoint": endpoint, "origem": request.headers.get("Origin")},
                        )
                    return jsonify({"erro": "Origin not allowed."}), 403

            # Quem fez o pedido, para o log e para as rotas que precisam de o saber
            request.environ["hermes.token"] = identidade

            # So os pedidos autenticados ficam registados como "chamada": um
            # pedido rejeitado ja fica em erro_autenticacao/acesso_negado, e o
            # corpo de um pedido nao autenticado (controlado por quem o envia)
            # nao deve ser copiado para o log.
            # get_json(silent=True): an empty or malformed body must be logged as
            # {}, never raise and turn the request into a 400.
            self.api_logger.log_chamada(
                endpoint=endpoint,
                metodo=request.method,
                token=token,
                payload=request.get_json(silent=True) or {},
                utilizador=identidade.get("nome"),
            )

            return func(*args, **kwargs)
        return wrapper

    def _responder(self, endpoint, dados, webhook_evento=None):
        self.api_logger.log_resposta(endpoint, dados)

        if webhook_evento:
            try:
                self.webhooks.enviar(webhook_evento)
            except Exception:
                self.logger.warn(f"Failed to send API webhook ({endpoint}).")

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

        @self.app.route("/auth/bootstrap", methods=["POST"])
        def auth_bootstrap():
            """Troca o nonce de arranque por uma cookie de sessao HttpOnly."""
            dados = request.json or {}
            sid = self.bootstrap.trocar(dados.get("nonce"), request.remote_addr)
            if sid is None:
                self.api_logger.log_acesso_negado(
                    "/auth/bootstrap",
                    "Startup nonce invalid, expired or already used",
                )
                return jsonify({"erro": "Invalid nonce."}), 403

            resposta = jsonify({"ok": True})
            resposta.set_cookie("hermes_session", sid, httponly=True, samesite="Strict", path="/")
            self.api_logger.log_chamada(
                "/auth/bootstrap", "POST", None, {}, utilizador="local",
            )
            return resposta

        @self.app.route("/auth/logout", methods=["POST"])
        def auth_logout():
            self.bootstrap.revogar(request.cookies.get("hermes_session"))
            resposta = jsonify({"ok": True})
            resposta.delete_cookie("hermes_session", path="/")
            return resposta

        @self.app.route("/status", methods=["GET"])
        @self._require_token
        def status():
            cache_key = "status"
            resposta_cache = self.cache.obter(cache_key)
            if resposta_cache:
                return self._responder("/status", resposta_cache)

            stats = self.metrics.obter_estatisticas()
            resposta = {
                "status": "Hermes PURPLE active",
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
                webhook_evento={"tipo": "comando", "descricao": "Command executed via PURPLE API",
                                "comando": cmd, "valor": valor, "resultado": resultado},
            )

        @self.app.route("/alerta", methods=["POST"])
        @self._require_token
        def alerta_manual():
            dados = request.json or {}
            descricao = dados.get("descricao", "Manual alert via API")
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
                self.api_logger.log_acesso_negado("/config", "Invalid key")
                return jsonify({"erro": "Invalid configuration key"}), 400

            self.config.atualizar(chave, valor)
            resposta = {"resultado": f"Configuration '{chave}' set to {valor}"}
            self.cache.guardar("config", resposta)

            return self._responder(
                "/config", resposta,
                webhook_evento={"tipo": "config", "descricao": "PURPLE configuration changed via API", "chave": chave, "valor": valor},
            )

        @self.app.route("/token/regenerar", methods=["POST"])
        @self._require_token
        def regenerar_token():
            """Revoga o token apresentado e emite um novo com o mesmo nome.

            O token e gerado pelo servidor com secrets.token_hex(32). A versao
            anterior aceitava uma "base" do chamador (por omissao
            "hermes-default") e calculava sha256(base): o token resultante era
            previsivel e publico, porque a base por omissao esta no codigo.

            A resposta nao passa por _responder(): esse caminho escreve a
            resposta no log, e o token novo iria para o ficheiro de log.
            """
            identidade = request.environ.get("hermes.token") or {}
            novo_token = self.auth.regenerar(identidade.get("id"))
            if novo_token is None:
                return jsonify({"erro": "Unknown token."}), 404

            self.api_logger.log_token_regenerado(novo_token)

            # O evento do webhook diz que houve rotacao; o token nunca entra nele.
            try:
                if getattr(self, "webhooks", None) is not None:
                    self.webhooks.enviar({"tipo": "token", "descricao": "Token regenerado via API PURPLE"})
            except Exception:
                if getattr(self, "logger", None) is not None:
                    self.logger.warn("Failed to send token rotation webhook.")

            return jsonify({
                "novo_token": novo_token,
                "aviso": "Save this token now: it will not be shown again.",
            }), 200

        @self.app.route("/dashboard", methods=["GET"])
        @self._require_token
        def dashboard():
            if self.dashboard is None:
                return jsonify({"erro": "Dashboard is not configured."}), 501

            dados = self.dashboard.gerar_dashboard()
            return self._responder("/dashboard", dados)

        @self.app.route("/dashboard/view", methods=["GET"])
        def dashboard_view():
            """
            Serve apenas a "casca" da pagina do dashboard: HTML e JavaScript,
            sem dados e sem token lá dentro. Os dados continuam a vir de
            /dashboard, que exige o cabecalho com o token. Como a casca nao
            expoe nada, pode ser servida sem autenticacao - e e o que permite
            abrir o dashboard no browser (uma navegacao nao consegue enviar
            cabecalhos) sem voltar a por o token na URL.
            """
            if self.dashboard is None:
                return "<h1>Dashboard is not configured.</h1>", 501

            recusa = self._recusar_token_na_url(request.path)
            if recusa is not None:
                return recusa

            return Response(_DASHBOARD_HTML, mimetype="text/html")

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

            # lab_boundary so faz sentido para tools cujo "alvo" e um IP/rede
            # real (nmap, openvas) - o seu objetivo e impedir scans fora do
            # lab autorizado. Para tshark (interface de rede, ex: "lo") e
            # suricata/zeek (caminho de ficheiro de log), o "alvo" nao e um
            # endereco de rede alcancavel - e sempre local por natureza,
            # tal como ja acontecia no caminho da IA (tool_dispatcher.py,
            # tipo_alvo="interface_fixa"). Validar "lo" como se fosse um IP
            # rejeitava sempre, por design - nao era um bug do boundary em
            # si, era o tipo errado de dado a passar por ele.
            FERRAMENTAS_BASEADAS_EM_IP = {"nmap", "openvas"}
            if tool in FERRAMENTAS_BASEADAS_EM_IP and not alvo_permitido(target):
                alerta = self.alerts.emitir_alerta(
                    severidade="SECURITY",
                    origem="lab_boundary",
                    descricao=f"Blocked out-of-lab target attempt: {target} (tool={tool})",
                    contexto={"tool": tool, "target": target},
                )
                return jsonify({
                    "error": f"Target '{target}' is outside the authorized lab boundary. Attempt logged.",
                }), 403

            try:
                eventos = ler_uma_vez_todas({tool: target})
            except Exception as e:
                self.logger.error(f"Failed to run '{tool}' against '{target}': {e}")
                self.alerts.emitir_alerta(
                    severidade="ERROR",
                    origem=tool,
                    descricao=f"Execution failed: {e}",
                    contexto={"tool": tool, "target": target},
                )
                return jsonify({
                    "error": (
                        f"The tool '{tool}' failed to run against '{target}': {e}. "
                        "Note: tshark expects a network interface "
                        "(e.g. 'lo', 'eth0'), suricata/zeek a log file path, and nmap/openvas an IP."
                    ),
                }), 500

            for evento in eventos:
                self.alerts.emitir_alerta(
                    severidade=str(evento.get("severidade") or "INFO"),
                    origem=evento.get("origem", tool),
                    descricao=evento.get("assinatura", "Event found"),
                    contexto=evento,
                )

            # Relatorio desta execucao especifica (2026-08-30, modo manual -
            # ver nota em hermes/purple/purple_runner.py sobre a decisao de
            # desligar a autonomia). Nunca deve rebentar a resposta - se
            # falhar, escrever_relatorio_execucao() ja devolve uma mensagem
            # clara em vez de propagar excecao, mas mantem-se o try/except
            # aqui por seguranca extra.
            relatorio = ""
            try:
                from hermes.core.hermes_intelligence import HermesIntelligence
                from hermes.core.intelligence_service import make_intelligence_service
                from hermes.core.context_builder import ContextConfig
                from pathlib import Path as _Path

                servico = make_intelligence_service(
                    HermesIntelligence(),
                    context_config=ContextConfig(clean_dir=_Path("hermes/runtime/clean")),
                )
                relatorio = servico.escrever_relatorio_execucao(tool, target, eventos)
            except Exception as e:
                relatorio = f"The report for this run could not be generated: {e}"

            return self._responder(
                "/run_tool",
                {
                    "tool": tool,
                    "target": target,
                    "events_found": len(eventos),
                    "events": eventos,
                    "relatorio": relatorio,
                },
            )

    def iniciar(self, porta=5000):
        """
        Arranca o servidor Flask. Corre em thread separada, arrancada
        pelo purple_runner.
        """
        self.logger.info(f"PURPLE API starting on port {porta}.")
        # threaded=True (2026-08-30): sem isto, o servidor de desenvolvimento
        # do Flask e single-threaded - um pedido longo (ex: /run_tool com
        # openvas, que pode demorar minutos) bloqueava TODOS os outros
        # pedidos, incluindo o polling do dashboard a cada 5s. Confirmado
        # como causa provavel de erros de rede no browser durante execucoes
        # longas.
        self.app.run(host=endereco_bind(), port=porta, use_reloader=False, threaded=True)


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
<h1>Hermes — PURPLE Dashboard</h1>
<div class="sub">Refreshes automatically every 5s · <span id="ultima-atualizacao" class="status">loading...</span></div>

<div class="card" id="login" style="margin-bottom:24px; display:none;">
  <h2>Access token</h2>
  <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
    <input id="token-input" type="password" autocomplete="off" placeholder="paste the token Hermes printed in the terminal"
           style="background:#0f1117; color:#e6e6e6; border:1px solid #30363d; padding:8px; border-radius:6px; flex:1; min-width:240px;">
    <button id="token-entrar" style="background:#238636; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer;">Sign in</button>
  </div>
  <div id="token-msg" style="font-size:0.8rem; color:#f85149; margin-top:6px;"></div>
</div>

<div class="grid" id="cartoes"></div>

<h2 style="color:#8b949e; font-size:0.9rem;">Run a tool</h2>
<div class="card" style="margin-bottom:24px; display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
  <select id="ferramenta" style="background:#0f1117; color:#e6e6e6; border:1px solid #30363d; padding:8px; border-radius:6px;">
    <option value="nmap">nmap</option>
    <option value="tshark">tshark</option>
    <option value="suricata">suricata</option>
    <option value="zeek">zeek</option>
    <option value="openvas">openvas</option>
  </select>
  <input id="alvo" type="text" value="127.0.0.1" style="background:#0f1117; color:#e6e6e6; border:1px solid #30363d; padding:8px; border-radius:6px; flex:1; min-width:160px;">
  <span id="ajuda-alvo" style="font-size:0.75rem; color:#8b949e; width:100%;">nmap/openvas: IP (e.g. 127.0.0.1) · tshark: network interface (e.g. lo) · suricata/zeek: path to the log file</span>
  <button id="btn-correr" style="background:#238636; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer;">Run</button>
  <span id="resultado-correr" style="font-size:0.85rem;"></span>
</div>

<h2 style="color:#8b949e; font-size:0.9rem;">Last run report</h2>
<div class="card" id="relatorio-execucao" style="margin-bottom:24px; line-height:1.5; white-space:pre-wrap;">
  <div class="vazio">Run a tool above to see the report here.</div>
</div>

<h2 style="color:#8b949e; font-size:0.9rem;">Events by source</h2>
<div class="grid" id="origens" style="margin-bottom:24px;"></div>

<h2 style="color:#8b949e; font-size:0.9rem;">Recent alerts</h2>
<table id="tabela-alertas">
  <thead><tr><th>Time</th><th>Source</th><th>Description</th></tr></thead>
  <tbody><tr><td colspan="3" class="vazio">loading...</td></tr></tbody>
</table>

<script>
// Nenhum HTML e construido a partir de dados: descricoes de alertas, nomes de
// assinaturas e nomes de interface vem de fora (Suricata, correlator, ficheiros
// de log) e entram sempre por textContent. Com uma sessao por cookie, um
// innerHTML aqui seria XSS armazenado com acesso directo a API.
const $ = (id) => document.getElementById(id);

let TOKEN = sessionStorage.getItem("hermes_token") || "";
let SESSAO = false;
let ULTIMO_ERRO = null;

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

function mostrarLogin(msg) {
  $("login").style.display = "block";
  $("token-msg").textContent = msg || "";
}

function esconderLogin() {
  $("login").style.display = "none";
  $("token-msg").textContent = "";
}

// O CLI abre a pagina com #n=<nonce>. O fragmento nunca chega ao servidor; e
// trocado por uma cookie HttpOnly e apagado do URL antes de qualquer pedido.
async function bootstrap() {
  const m = location.hash.match(/^#n=([0-9a-f]{64})$/);
  if (!m) return false;
  history.replaceState(null, "", location.pathname + location.search);
  try {
    const r = await fetch("/auth/bootstrap", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({nonce: m[1]}),
    });
    return r.ok;
  } catch (e) {
    return false;
  }
}

function pedir(url, opcoes = {}) {
  const headers = Object.assign({}, opcoes.headers || {});
  if (SESSAO) {
    // Content-Type only when there is a body. A GET with Content-Type
    // application/json and no body makes the server try to parse the request as
    // JSON, which fails and turns every dashboard request into a 400.
    if (opcoes.body) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
  } else {
    headers["X-Hermes-Token"] = TOKEN;
  }
  return fetch(url, Object.assign({}, opcoes, {headers}));
}

async function entrar() {
  const campo = $("token-input");
  const valor = campo.value.trim();
  if (!valor) return;
  TOKEN = valor;
  SESSAO = false;
  const ok = await atualizar();
  if (ok) {
    sessionStorage.setItem("hermes_token", valor);
    campo.value = "";
    esconderLogin();
  } else {
    TOKEN = "";
    if (!ULTIMO_ERRO || ULTIMO_ERRO.status === 403) {
      $("token-msg").textContent = "Invalid token.";
    } else if (ULTIMO_ERRO.rede) {
      $("token-msg").textContent = "Cannot reach the server.";
    } else {
      $("token-msg").textContent = "HTTP error " + ULTIMO_ERRO.status + ".";
    }
  }
}

$("token-entrar").addEventListener("click", entrar);
$("token-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") entrar();
});

async function atualizar() {
  if (!SESSAO && !TOKEN) {
    $("ultima-atualizacao").textContent = "no session";
    mostrarLogin("");
    return false;
  }
  try {
    const r = await pedir("/dashboard");
    if (!r.ok) {
      ULTIMO_ERRO = {status: r.status};
      if (r.status === 403) {
        SESSAO = false;
        TOKEN = "";
        sessionStorage.removeItem("hermes_token");
        mostrarLogin("Session expired. Paste the token or restart Hermes.");
      }
      $("ultima-atualizacao").textContent = "update error: HTTP " + r.status;
      return false;
    }
    const d = await r.json();
    const metricas = d.metricas || {};
    const contadores = metricas.contadores || {};
    const alertas = d.alertas_recentes || [];

    $("cartoes").replaceChildren(
      cartao("Status", d.estado || "?"),
      cartao("Heartbeats PURPLE", contadores.heartbeat_purple || 0),
      cartao("Health-check failures (this run)", contadores.healthcheck_falha || 0),
      cartao("Operation", "manual")
    );

    const contagem = new Map();
    alertas.forEach((a) => {
      const origem = a.origem || (a.evento && a.evento.origem) || "unknown";
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
          origem.textContent = a.origem || (a.evento && a.evento.origem) || "-";
          const desc = document.createElement("td");
          desc.textContent = a.descricao || (a.evento && a.evento.assinatura) || JSON.stringify(a).slice(0, 80);
          tr.append(quando, origem, desc);
          return tr;
        })
      );
    }

    $("ultima-atualizacao").textContent = "last update: " + new Date().toLocaleTimeString();
    return true;
  } catch (e) {
    ULTIMO_ERRO = {rede: true};
    $("ultima-atualizacao").textContent = "update error: " + e;
    return false;
  }
}

document.getElementById("ferramenta").addEventListener("change", () => {
  const tool = document.getElementById("ferramenta").value;
  const alvoEl = document.getElementById("alvo");
  const valoresDefeito = {
    nmap: "127.0.0.1",
    openvas: "127.0.0.1",
    tshark: "lo",
    suricata: "/var/log/suricata/eve.json",
    zeek: "/opt/zeek/logs/current/conn.log",
  };
  alvoEl.value = valoresDefeito[tool] || "127.0.0.1";
});

document.getElementById("btn-correr").addEventListener("click", async () => {
  if (!SESSAO && !TOKEN) {
    mostrarLogin("");
    return;
  }
  const tool = document.getElementById("ferramenta").value;
  const target = document.getElementById("alvo").value;
  const resultadoEl = document.getElementById("resultado-correr");
  const relatorioEl = document.getElementById("relatorio-execucao");

  resultadoEl.textContent = "Running... (can take up to 2 min, especially for openvas)";
  resultadoEl.style.color = "#8b949e";
  relatorioEl.textContent = "generating report...";

  try {
    const r = await pedir("/run_tool", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({tool, target}),
    });
    const d = await r.json();

    if (!r.ok) {
      resultadoEl.textContent = d.error || "Blocked.";
      resultadoEl.style.color = "#f85149";
      relatorioEl.textContent = d.error || "Blocked.";
    } else {
      resultadoEl.textContent = d.events_found + " event(s) found.";
      resultadoEl.style.color = "#7ee787";
      relatorioEl.textContent = d.relatorio || "(no report)";
      atualizar();
    }
  } catch (e) {
    resultadoEl.textContent = "Error: " + e;
    resultadoEl.style.color = "#f85149";
    relatorioEl.textContent = "Error: " + e;
  }
});

(async () => {
  const temNonce = location.hash.startsWith("#n=");
  if (temNonce) {
    // The nonce exists only in this load: if the exchange fails there is no
    // session to fall back on.
    SESSAO = await bootstrap();
  } else if (!TOKEN) {
    // Reload or a second tab: the cookie may be valid. Assume it is and let the
    // 403 from atualizar() reset the state, instead of showing a token box to
    // someone who is already signed in.
    SESSAO = true;
  }
  if (!SESSAO && !TOKEN) {
    mostrarLogin("");
  } else {
    esconderLogin();
  }
  atualizar();
  setInterval(atualizar, 5000);
})();

</script>
</body>
</html>
"""
