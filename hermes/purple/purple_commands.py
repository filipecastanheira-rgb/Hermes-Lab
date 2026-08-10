import time

class PurpleCommands:
    """
    Sistema de comandos internos para o modo PURPLE.
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
            self.logger.escrever("COMANDO — eventos simulados pausados.")
            return "Eventos simulados pausados."

        elif comando == "retomar_eventos":
            self.config.atualizar("simulacao_eventos", True)
            self.logger.escrever("COMANDO — eventos simulados retomados.")
            return "Eventos simulados retomados."

        elif comando == "set_heartbeat":
            try:
                valor = int(valor)
                self.config.atualizar("intervalo_heartbeat", valor)
                self.logger.escrever(f"COMANDO — intervalo heartbeat atualizado para {valor}.")
                return f"Heartbeat atualizado para {valor} ciclos."
            except:
                return "Valor inválido para heartbeat."

        elif comando == "set_healthcheck":
            try:
                valor = int(valor)
                self.config.atualizar("intervalo_healthcheck", valor)
                self.logger.escrever(f"COMANDO — intervalo healthcheck atualizado para {valor}.")
                return f"Health-check atualizado para {valor} ciclos."
            except:
                return "Valor inválido para health-check."

        elif comando == "set_metricas":
            try:
                valor = int(valor)
                self.config.atualizar("intervalo_metricas", valor)
                self.logger.escrever(f"COMANDO — intervalo métricas atualizado para {valor}.")
                return f"Métricas atualizadas para {valor} ciclos."
            except:
                return "Valor inválido para métricas."

        elif comando == "forcar_healthcheck":
            self.logger.escrever("COMANDO — health-check forçado manualmente.")
            self.alerts.emitir_alerta(
                severidade="INFO",
                origem="comandos",
                descricao="Health-check forçado manualmente."
            )
            return "Health-check forçado."

        elif comando == "mostrar_config":
            self.logger.escrever("COMANDO — mostrar configuração atual.")
            self.config.imprimir()
            return "Configuração mostrada na consola."

        elif comando == "alerta_manual":
            self.alerts.emitir_alerta(
                severidade="ALTO",
                origem="comandos",
                descricao="Alerta manual emitido.",
                contexto={"timestamp": time.time()}
            )
            return "Alerta manual emitido."

        else:
            return f"Comando desconhecido: {comando}"

