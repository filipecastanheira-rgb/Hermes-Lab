import json
import time
import os


class Metrics:
    """
    Sistema de métricas persistentes para o modo PURPLE.
    Guarda:
    - contadores
    - latências
    - eventos internos
    - histórico rotativo

    Ficheiros:
    - runtime/metrics/purple_metrics.json
    - runtime/metrics/purple_metrics_history.json
    """

    def __init__(self,
                 ficheiro_atual="runtime/metrics/purple_metrics.json",
                 ficheiro_historico="runtime/metrics/purple_metrics_history.json",
                 max_historico=500):

        os.makedirs(os.path.dirname(ficheiro_atual), exist_ok=True)

        self.ficheiro_atual = ficheiro_atual
        self.ficheiro_historico = ficheiro_historico
        self.max_historico = max_historico

        # Carregar métricas existentes ou iniciar novas
        self.metricas = self._carregar_metricas()

    # ============================================================
    # Carregar métricas persistidas
    # ============================================================
    def _carregar_metricas(self):
        if os.path.exists(self.ficheiro_atual):
            try:
                with open(self.ficheiro_atual, "r") as f:
                    return json.load(f)
            except Exception:
                pass

        # Estrutura inicial
        return {
            "contadores": {},
            "latencias": {},
            "eventos": [],
            "ultimo_update": time.time()
        }

    # ============================================================
    # Guardar métricas no ficheiro
    # ============================================================
    def _guardar_metricas(self):
        self.metricas["ultimo_update"] = time.time()

        with open(self.ficheiro_atual, "w") as f:
            json.dump(self.metricas, f, ensure_ascii=False, indent=2)

    # ============================================================
    # Guardar histórico rotativo
    # ============================================================
    def _guardar_historico(self, evento):
        historico = []

        if os.path.exists(self.ficheiro_historico):
            try:
                with open(self.ficheiro_historico, "r") as f:
                    historico = json.load(f)
            except Exception:
                historico = []

        historico.append(evento)

        # Rotação
        if len(historico) > self.max_historico:
            historico = historico[-self.max_historico:]

        with open(self.ficheiro_historico, "w") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)

    # ============================================================
    # Incrementar contadores
    # ============================================================
    def incrementar(self, chave):
        self.metricas["contadores"][chave] = self.metricas["contadores"].get(chave, 0) + 1

        self._guardar_metricas()
        self._guardar_historico({
            "timestamp": time.time(),
            "tipo": "contador",
            "chave": chave,
            "valor": self.metricas["contadores"][chave]
        })

    # ============================================================
    # Registar latência
    # ============================================================
    def registar_latencia(self, chave, valor):
        self.metricas["latencias"][chave] = valor

        self._guardar_metricas()
        self._guardar_historico({
            "timestamp": time.time(),
            "tipo": "latencia",
            "chave": chave,
            "valor": valor
        })

    # ============================================================
    # Registar evento interno
    # ============================================================
    def registar_evento(self, descricao, contexto=None):
        evento = {
            "timestamp": time.time(),
            "descricao": descricao,
            "contexto": contexto or {}
        }

        self.metricas["eventos"].append(evento)

        # Rotação interna
        if len(self.metricas["eventos"]) > 200:
            self.metricas["eventos"] = self.metricas["eventos"][-200:]

        self._guardar_metricas()
        self._guardar_historico({
            "timestamp": time.time(),
            "tipo": "evento",
            "descricao": descricao,
            "contexto": contexto or {}
        })

    # ============================================================
    # Obter estatísticas completas
    # ============================================================
    def obter_estatisticas(self):
        return self.metricas

