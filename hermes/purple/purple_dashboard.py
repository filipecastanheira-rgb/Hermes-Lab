import json
import time
import os


class PurpleDashboard:
    """
    Dashboard consolidado do modo PURPLE.
    Agrega:
    - métricas atuais
    - histórico
    - alertas recentes
    - estado do runner
    - configuração ativa
    """

    def __init__(self,
                 metrics,
                 alerts,
                 config,
                 ficheiro_historico="runtime/metrics/purple_metrics_history.json",
                 ficheiro_alertas="logs/purple_alerts.json"):

        self.metrics = metrics
        self.alerts = alerts
        self.config = config
        self.ficheiro_historico = ficheiro_historico
        self.ficheiro_alertas = ficheiro_alertas

        # Garantir diretórios
        os.makedirs(os.path.dirname(ficheiro_historico), exist_ok=True)
        os.makedirs(os.path.dirname(ficheiro_alertas), exist_ok=True)

    # ============================================================
    # Carregar histórico de métricas
    # ============================================================
    def _carregar_historico(self):
        if os.path.exists(self.ficheiro_historico):
            try:
                with open(self.ficheiro_historico, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    # ============================================================
    # Carregar alertas recentes
    # ============================================================
    def _carregar_alertas(self):
        if os.path.exists(self.ficheiro_alertas):
            try:
                with open(self.ficheiro_alertas, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    # ============================================================
    # Construir dashboard consolidado
    # ============================================================
    def gerar_dashboard(self):
        metricas_atuais = self.metrics.obter_estatisticas()
        historico = self._carregar_historico()
        alertas = self._carregar_alertas()

        dashboard = {
            "timestamp": time.time(),
            "modo": "PURPLE",
            "estado": "ativo",
            "config": self.config.config,
            "metricas": metricas_atuais,
            "historico_metricas": historico[-50:],  # últimos 50 eventos
            "alertas_recentes": alertas[-50:],      # últimos 50 alertas
        }

        return dashboard

