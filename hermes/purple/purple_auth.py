import json
import os
import time
import hashlib

class PurpleAuth:
    """
    Sistema de autenticação por token para a API PURPLE.
    """

    def __init__(self, ficheiro="config/purple_auth.json"):
        self.ficheiro = ficheiro
        os.makedirs(os.path.dirname(ficheiro), exist_ok=True)

        if not os.path.exists(self.ficheiro):
            self._criar_auth_inicial()

        self.auth = self._carregar()

    def _criar_auth_inicial(self):
        token_inicial = self._gerar_token("hermes-default")

        dados = {
            "token": token_inicial,
            "criado_em": time.ctime(),
            "descricao": "Token inicial gerado automaticamente."
        }

        with open(self.ficheiro, "w") as f:
            json.dump(dados, f, indent=4)

    def _carregar(self):
        with open(self.ficheiro, "r") as f:
            return json.load(f)

    def _guardar(self):
        with open(self.ficheiro, "w") as f:
            json.dump(self.auth, f, indent=4)

    def _gerar_token(self, base):
        hash_obj = hashlib.sha256(base.encode())
        return hash_obj.hexdigest()

    def validar(self, token_recebido):
        return token_recebido == self.auth["token"]

    def atualizar_token(self, novo_base):
        novo_token = self._gerar_token(novo_base)
        self.auth["token"] = novo_token
        self.auth["criado_em"] = time.ctime()
        self._guardar()
        return novo_token

    def mostrar(self):
        print("\n[AUTH PURPLE] Token atual:")
        print(f" - token: {self.auth['token']}")
        print(f" - criado em: {self.auth['criado_em']}")
        print(f" - descricao: {self.auth['descricao']}\n")

