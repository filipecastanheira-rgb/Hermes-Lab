import time

class PurpleCommands:
    """
    Sistema de comandos internos para o camada PURPLE.
    Permite controlar o pipeline contínuo em tempo real.
    """

    def __init__(self, config, logger, alerts):
        self.config = config
        self.logger = logger
        self.alerts = alerts

    def executar(self, comando, valor=None):
        comando = comando.lower()

        if comando == "pausar_eventos":
            self.config.atualizar("simulacao_eventos", False)
            self.logger.escrever("COMMAND — simulated events paused.")
            return "Simulated events paused."

        elif comando == "retomar_eventos":
            self.config.atualizar("simulacao_eventos", True)
            self.logger.escrever("COMMAND — simulated events resumed.")
            return "Simulated events resumed."

        elif comando == "set_heartbeat":
            try:
                valor = int(valor)
                self.config.atualizar("intervalo_heartbeat", valor)
                self.logger.escrever(f"COMMAND — heartbeat interval set to {valor}.")
                return f"Heartbeat interval set to {valor} cycles."
            except:
                return "Invalid value for heartbeat."

        elif comando == "set_healthcheck":
            try:
                valor = int(valor)
                self.config.atualizar("intervalo_healthcheck", valor)
                self.logger.escrever(f"COMMAND — health-check interval set to {valor}.")
                return f"Health-check interval set to {valor} cycles."
            except:
                return "Invalid value for health-check."

        elif comando == "set_metricas":
            try:
                valor = int(valor)
                self.config.atualizar("intervalo_metricas", valor)
                self.logger.escrever(f"COMMAND — metrics interval set to {valor}.")
                return f"Metrics interval set to {valor} cycles."
            except:
                return "Invalid value for metrics."

        elif comando == "forcar_healthcheck":
            self.logger.escrever("COMMAND — health-check forced manually.")
            self.alerts.emitir_alerta(
                severidade="INFO",
                origem="comandos",
                descricao="Health-check forced manually."
            )
            return "Health-check forced."

        elif comando == "mostrar_config":
            self.logger.escrever("COMMAND — show current configuration.")
            self.config.imprimir()
            return "Configuration shown on the console."

        elif comando == "alerta_manual":
            self.alerts.emitir_alerta(
                severidade="ALTO",
                origem="comandos",
                descricao="Manual alert emitted.",
                contexto={"timestamp": time.time()}
            )
            return "Manual alert emitted."

        else:
            return f"Unknown command: {comando}"

