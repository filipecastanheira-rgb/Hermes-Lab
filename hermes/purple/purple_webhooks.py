import json
import requests
import time
import os

class PurpleWebhooks:
    """
    Sistema de webhooks do Hermes PURPLE.
    Permite enviar alertas e eventos para serviços externos.
    """

    def __init__(self, ficheiro="config/purple_webhooks.json"):
        self.ficheiro = ficheiro
        os.makedirs(os.path.dirname(ficheiro), exist_ok=True)

        if not os.path.exists(self.ficheiro):
            self._criar_config_inicial()

        self.config = self._carregar()

    def _criar_config_inicial(self):
        dados = {
            "ativo": False,
            "urls": [],
            "timeout": 3,
            "retries": 2
        }
        with open(self.ficheiro, "w") as f:
            json.dump(dados, f, indent=4)

    def _carregar(self):
        with open(self.ficheiro, "r") as f:
            return json.load(f)

    def _guardar(self):
        with open(self.ficheiro, "w") as f:
            json.dump(self.config, f, indent=4)

    def ativar(self):
        self.config["ativo"] = True
        self._guardar()

    def desativar(self):
        self.config["ativo"] = False
        self._guardar()

    def adicionar_url(self, url):
        self.config["urls"].append(url)
        self._guardar()

    def remover_url(self, url):
        if url in self.config["urls"]:
            self.config["urls"].remove(url)
            self._guardar()

    def enviar(self, evento):
        """
        Envia o evento para todas as URLs configuradas.
        """

        if not self.config["ativo"]:
            return False

        urls = self.config["urls"]
        timeout = self.config["timeout"]
        retries = self.config["retries"]

        payload = {
            "timestamp": time.time(),
            "evento": evento
        }

        resultados = []

        for url in urls:
            sucesso = False

            for tentativa in range(retries):
                try:
                    r = requests.post(url, json=payload, timeout=timeout)
                    if r.status_code in (200, 201, 204):
                        sucesso = True
                        break
                except Exception:
                    time.sleep(0.2)

            resultados.append({
                "url": url,
                "sucesso": sucesso
            })

        return resultados

