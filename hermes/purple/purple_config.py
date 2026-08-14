import json
import os
import time

class PurpleConfig:
    """
    Sistema de configuração dinâmica para o modo PURPLE.
    Permite alterar parâmetros sem reiniciar o Hermes.
    """

    def __init__(self, ficheiro="config/purple_config.json"):
        self.ficheiro = ficheiro
        os.makedirs(os.path.dirname(ficheiro), exist_ok=True)

        # Se não existir, criar config inicial
        if not os.path.exists(self.ficheiro):
            self._criar_config_inicial()

        self.config = self._carregar()

    def _criar_config_inicial(self):
        config_inicial = {
            "intervalo_heartbeat": 1,
            "intervalo_healthcheck": 10,
            "intervalo_metricas": 15,
            "nivel_alerta_minimo": "INFO",
            "simulacao_eventos": True
        }

        with open(self.ficheiro, "w") as f:
            json.dump(config_inicial, f, indent=4)

    def _carregar(self):
        with open(self.ficheiro, "r") as f:
            return json.load(f)

    def obter(self, chave):
        return self.config.get(chave)

    def atualizar(self, chave, valor):
        self.config[chave] = valor
        self._guardar()
        print(f"[CONFIG PURPLE] '{chave}' atualizado para: {valor}")

    def _guardar(self):
        with open(self.ficheiro, "w") as f:
            json.dump(self.config, f, indent=4)

    def imprimir(self):
        print("\n[CONFIG PURPLE] Configuração atual:")
        for chave, valor in self.config.items():
            print(f" - {chave}: {valor}")
        print()

