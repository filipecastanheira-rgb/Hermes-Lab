import time
import os
import json

class PurpleRateLimit:
    """
    Sistema de rate limiting para a API PURPLE.
    Limita pedidos por token ou IP.
    """

    def __init__(self, max_por_minuto=60, ficheiro="config/purple_ratelimit.json"):
        self.max_por_minuto = max_por_minuto
        self.ficheiro = ficheiro

        os.makedirs(os.path.dirname(ficheiro), exist_ok=True)

        if not os.path.exists(self.ficheiro):
            self._criar_registo_inicial()

        self.registos = self._carregar()

    def _criar_registo_inicial(self):
        dados = {
            "tokens": {},
            "ips": {}
        }
        with open(self.ficheiro, "w") as f:
            json.dump(dados, f, indent=4)

    def _carregar(self):
        with open(self.ficheiro, "r") as f:
            return json.load(f)

    def _guardar(self):
        with open(self.ficheiro, "w") as f:
            json.dump(self.registos, f, indent=4)

    def _limpar_antigos(self, lista):
        agora = time.time()
        return [t for t in lista if agora - t < 60]

    def verificar_token(self, token):
        if token not in self.registos["tokens"]:
            self.registos["tokens"][token] = []

        timestamps = self.registos["tokens"][token]
        timestamps = self._limpar_antigos(timestamps)

        if len(timestamps) >= self.max_por_minuto:
            return False  # rate limit excedido

        timestamps.append(time.time())
        self.registos["tokens"][token] = timestamps
        self._guardar()
        return True

    def verificar_ip(self, ip):
        if ip not in self.registos["ips"]:
            self.registos["ips"][ip] = []

        timestamps = self.registos["ips"][ip]
        timestamps = self._limpar_antigos(timestamps)

        if len(timestamps) >= self.max_por_minuto:
            return False  # rate limit excedido

        timestamps.append(time.time())
        self.registos["ips"][ip] = timestamps
        self._guardar()
        return True

