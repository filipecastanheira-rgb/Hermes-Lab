import json
import time
import os

from hermes.core.context_builder import ContextConfig, load_events


class PurpleDashboard:
    """
    Dashboard consolidado do modo PURPLE.
    Agrega:
    - métricas atuais
    - histórico
    - alertas recentes
    - estado do runner
    - configuração ativa
    - último relatório da IA (2026-08-29)
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
    # Obter o relatório mais recente da IA (clean/, event_type="relatorio")
    # ============================================================
    def _obter_ultimo_relatorio(self):
        """
        Vai buscar o relatorio mais recente da IA aos eventos clean/.
        Janela alargada (48h, > que o intervalo diario de fallback de
        24h em purple_runner) para o cartao nao ficar vazio logo a
        seguir a fronteira das 24h. Nunca rebenta o dashboard - se
        falhar, devolve None e o HTML mostra "ainda sem relatorio".
        """
        try:
            eventos = load_events(
                ContextConfig(lookback_hours=48),
                event_type="relatorio",
            )
        except Exception:
            return None

        if not eventos:
            return None

        mais_recente = eventos[0]  # load_events ja ordena mais recente primeiro
        dados = mais_recente.get("data", {}) or {}
        return {
            "texto": dados.get("texto", ""),
            "motivo": dados.get("motivo", ""),
            "timestamp": mais_recente.get("timestamp"),
        }
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
            "ultimo_relatorio": self._obter_ultimo_relatorio(),
        }
        return dashboard
