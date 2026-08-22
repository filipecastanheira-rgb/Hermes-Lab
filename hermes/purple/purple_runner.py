"""
purple_runner.py
Runner principal do modo PURPLE.

Corrigido face ao original (tudo testado):
- PurpleAlerts(logger, metrics) -> a classe só aceita (logger)
- PurpleCommands(config, metrics, alerts, logger) -> ordem errada,
  a classe espera (config, logger, alerts)
- PurpleCache(ttl_segundos=5) -> o parâmetro chama-se ttl
- PurpleAPI(...) -> faltavam webhooks e dashboard
- HealthCheck(logger) do BLUE -> substituído por PurpleHealthCheck(self),
  que verifica os componentes reais do PURPLE
- watchdog.recuperar() -> substituído por PurpleWatchdog, que já tem
  esse método
- health-check dentro do loop agora está protegido por try/except,
  para nunca mais matar o processo todo por uma falha de um componente
"""

import threading
import time

from hermes.purple.purple_logger import PurpleLogger
from hermes.purple.purple_alerts import PurpleAlerts
from hermes.purple.purple_config import PurpleConfig
from hermes.purple.purple_commands import PurpleCommands
from hermes.purple.purple_api import PurpleAPI
from hermes.purple.purple_auth import PurpleAuth
from hermes.purple.purple_api_logger import PurpleAPILogger
from hermes.purple.purple_ratelimit import PurpleRateLimit
from hermes.purple.purple_cache import PurpleCache
from hermes.purple.purple_compression import PurpleCompression
from hermes.purple.purple_webhooks import PurpleWebhooks
from hermes.purple.purple_dashboard import PurpleDashboard
from hermes.purple.purple_health import PurpleHealthCheck
from hermes.purple.purple_watchdog import PurpleWatchdog

from hermes.utils.metrics import Metrics
from hermes.core.event_store import apply_retention
from hermes.modes.mode_router import ModeRouter
from hermes.tools.agregador_ferramentas import vigiar_todas
from pathlib import Path
from hermes.core.hermes_intelligence import HermesIntelligence
from hermes.core.intelligence_service import make_intelligence_service
from hermes.core.context_builder import ContextConfig


class PurpleRunner:
    def __init__(self):
        self.logger = PurpleLogger()
        self.config = PurpleConfig()
        self.metrics = Metrics()
        self.alerts = PurpleAlerts(self.logger)
        self.commands = PurpleCommands(self.config, self.logger, self.alerts)
        self.auth = PurpleAuth()
        self.api_logger = PurpleAPILogger()
        self.ratelimit = PurpleRateLimit()
        self.cache = PurpleCache(ttl=5)
        self.compression = PurpleCompression(ativo=True, nivel=5)
        self.webhooks = PurpleWebhooks()
        self.dashboard = PurpleDashboard(self.metrics, self.alerts, self.config)

        self.api = PurpleAPI(
            commands=self.commands,
            config=self.config,
            metrics=self.metrics,
            alerts=self.alerts,
            logger=self.logger,
            auth=self.auth,
            api_logger=self.api_logger,
            ratelimit=self.ratelimit,
            cache=self.cache,
            compression=self.compression,
            webhooks=self.webhooks,
            dashboard=self.dashboard,
        )
        self._ultima_retencao = 0
        self._intervalo_retencao = 3600  # correr a retenção 1x por hora
        self._ultima_decisao_ia = 0
        self._intervalo_decisao_ia = 300  # decisao autonoma da IA a cada 5 minutos
        self._intelligence_service = make_intelligence_service(
            HermesIntelligence(),
            context_config=ContextConfig(clean_dir=Path("hermes/runtime/clean")),
        )
        self._api_thread = threading.Thread(
            target=self.api.iniciar, kwargs={"porta": self.config.obter("api_port") or 5000}, daemon=True,
        )

        # Health-check e watchdog PRÓPRIOS do PURPLE — não os do BLUE
        self.health_check = PurpleHealthCheck(self)
        self.watchdog = PurpleWatchdog(self.logger)

    def iniciar(self):
        self.logger.info("A iniciar Hermes PURPLE...")

        try:
            self.webhooks.enviar({
                "tipo": "startup",
                "descricao": "Hermes PURPLE iniciado",
                "config": self.config.config,
            })
        except Exception:
            self.logger.warn("Falha ao enviar webhook de startup (PURPLE).")

        self._api_thread.start()
        self.logger.info("API PURPLE iniciada em thread separada.")
        # Arranca a vigilancia continua das ferramentas de fundo
        # (Suricata, Zeek) - Fase 0 raw/clean, nunca deve impedir o
        # PURPLE de arrancar se falhar.
        try:
            self._blue_router = ModeRouter("config/hermes_config.json")
            self._blue_router.iniciar()
            from hermes.core.dependency_manager import garantir_dependencias
            garantir_dependencias(self.logger)
            vigiar_todas(self._blue_router, {
                "suricata": "/var/log/suricata/eve.json",
                "zeek": "/opt/zeek/logs/current/conn.log",
            })
            self.logger.info("Vigilancia continua (Suricata/Zeek) iniciada.")
        except Exception as e:
            self.logger.error(f"Falha ao iniciar vigilancia continua: {e}")


        self._loop_principal()

    def _loop_principal(self):
        intervalo_heartbeat = self.config.obter("intervalo_heartbeat") or 5

        while True:
            inicio = time.time()

            self.logger.heartbeat("PURPLE ativo")
            self.metrics.incrementar("heartbeat_purple")

            # Health-check protegido — uma falha aqui NUNCA deve matar
            # o processo inteiro (era isto que acontecia antes)
            try:
                estado = self.health_check.verificar()
            except Exception as e:
                self.logger.error(f"Health-check PURPLE rebentou: {e}")
                estado = {"ok": False}

            if not estado.get("ok", True):
                self.logger.error("Health-check PURPLE falhou", extra=estado)
                self.metrics.incrementar("healthcheck_falha")

                try:
                    self.watchdog.recuperar(estado)
                except Exception as e:
                    self.logger.error(f"Watchdog rebentou: {e}")

            duracao = time.time() - inicio
            self.metrics.registar_latencia("loop_purple", duracao)

            # Retencao raw/+clean/ (Fase 0) - corre no maximo 1x/hora
            if time.time() - self._ultima_retencao >= self._intervalo_retencao:
                try:
                    removidos = apply_retention()
                    self.logger.info(f"Retencao aplicada: {removidos}")
                except Exception as e:
                    self.logger.error(f"Retencao falhou: {e}")
                self._ultima_retencao = time.time()
            # Decisao autonoma da IA (Fase 1: nmap/tshark, dentro do
            # lab_boundary, alvo sempre fixo - ver decide_action()).
            # Cada acao tomada (ou recusada) fica visivel no dashboard
            # via alertas, para o utilizador ver o que o Hermes esta
            # a fazer sem ter de escolher a ferramenta manualmente.
            if time.time() - self._ultima_decisao_ia >= self._intervalo_decisao_ia:
                try:
                    resultado = self._intelligence_service.decide_action(
                        "Ha algum evento recente que precise de investigacao?"
                    )
                    for acao in resultado.get("acoes", []):
                        r = acao["resultado"]
                        if r.get("ok"):
                            self.alerts.emitir_alerta(
                                severidade="INFO",
                                origem="hermes_ia",
                                descricao=f"IA correu '{r.get('ferramenta')}' em '{r.get('target')}'",
                                contexto={"eventos_capturados": len(r.get("eventos", []))},
                            )
                        else:
                            self.alerts.emitir_alerta(
                                severidade="INFO",
                                origem="hermes_ia",
                                descricao=f"IA tentou uma acao mas foi recusada: {r.get('erro')}",
                                contexto={},
                            )
                except Exception as e:
                    self.logger.error(f"Decisao autonoma da IA falhou: {e}")
                self._ultima_decisao_ia = time.time()

            time.sleep(intervalo_heartbeat)
