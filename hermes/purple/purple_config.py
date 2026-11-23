import json
import os
import time

INTERVALO_MIN = 1
INTERVALO_MAX = 3600
CHAVES_INTERVALO = ("intervalo_heartbeat", "intervalo_healthcheck", "intervalo_metricas")
NIVEIS_ALERTA = ("INFO", "ERROR")


class PurpleConfig:
    """
    Sistema de configuração dinâmica para o camada PURPLE.
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

    @staticmethod
    def _validar(chave, valor):
        """Raise ValueError if the value cannot be used by the runtime."""
        if chave in CHAVES_INTERVALO:
            if isinstance(valor, bool) or not isinstance(valor, int) \
                    or not INTERVALO_MIN <= valor <= INTERVALO_MAX:
                raise ValueError(
                    f"{chave} must be an integer between {INTERVALO_MIN} and {INTERVALO_MAX}")
        elif chave == "simulacao_eventos":
            if not isinstance(valor, bool):
                raise ValueError("simulacao_eventos must be true or false")
        elif chave == "nivel_alerta_minimo":
            if valor not in NIVEIS_ALERTA:
                raise ValueError(f"nivel_alerta_minimo must be one of {', '.join(NIVEIS_ALERTA)}")

    def atualizar(self, chave, valor):
        self._validar(chave, valor)
        self.config[chave] = valor
        self._guardar()
        print(f"[CONFIG PURPLE] '{chave}' set to: {valor}")

    def _guardar(self):
        with open(self.ficheiro, "w") as f:
            json.dump(self.config, f, indent=4)

    def imprimir(self):
        print("\n[CONFIG PURPLE] Current configuration:")
        for chave, valor in self.config.items():
            print(f" - {chave}: {valor}")
        print()

