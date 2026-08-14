import json
import time
import os


class PurpleLogger:
    """
    Logger estruturado em JSON para o modo PURPLE.
    Compatível com ELK, Splunk, Sentinel e qualquer SIEM moderno.
    """

    def __init__(self, ficheiro="logs/purple.log"):
        os.makedirs(os.path.dirname(ficheiro), exist_ok=True)
        self.ficheiro = ficheiro

    # ============================================================
    # Função interna para escrever JSON no ficheiro
    # ============================================================
    def _escrever(self, nivel, mensagem, extra=None):
        evento = {
            "timestamp": time.time(),
            "nivel": nivel,
            "mensagem": mensagem,
            "modo": "PURPLE"
        }

        if extra:
            evento["extra"] = extra

        linha = json.dumps(evento, ensure_ascii=False)

        with open(self.ficheiro, "a") as f:
            f.write(linha + "\n")

    # ============================================================
    # Métodos públicos de logging
    # ============================================================
    def info(self, mensagem, extra=None):
        self._escrever("INFO", mensagem, extra)

    def warn(self, mensagem, extra=None):
        self._escrever("WARN", mensagem, extra)

    def error(self, mensagem, extra=None):
        self._escrever("ERROR", mensagem, extra)

    def heartbeat(self, mensagem="heartbeat", extra=None):
        self._escrever("HEARTBEAT", mensagem, extra)

