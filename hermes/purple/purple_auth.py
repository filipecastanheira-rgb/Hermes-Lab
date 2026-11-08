"""Autenticacao por token da API PURPLE.

Em disco ficam apenas resumos SHA-256 dos tokens (formato 2 do ficheiro). O
token em claro existe no momento em que e criado e e mostrado uma unica vez:
depois disso, so quem o guardou o consegue apresentar. Um ficheiro lido por
engano (backup, copia para debug, sincronizacao para a cloud) deixa de dar
acesso a API.

A estrutura suporta varios tokens, um por pessoa ou dispositivo. E o que
permite revogar o acesso de alguem sem tocar nos restantes, e atribuir cada
pedido a um utilizador no log.
"""
import hashlib
import hmac
import json
import os
import secrets
import time

FORMATO = 2

# Valor que resultava de POST /token/regenerar sem corpo na versao anterior:
# sha256("hermes-default"). E publico, portanto nunca pode sobreviver a uma
# migracao - quem o tivesse conhecido mantinha o acesso para sempre.
TOKEN_PUBLICO_CONHECIDO = hashlib.sha256(b"hermes-default").hexdigest()


def hash_token(token):
    """Resumo do token. Nao reversivel: e isto que fica guardado em disco."""
    return hashlib.sha256(str(token).encode()).hexdigest()


class PurpleAuth:
    def __init__(self, ficheiro="config/purple_auth.json"):
        self.ficheiro = ficheiro
        pasta = os.path.dirname(ficheiro)
        if pasta:
            os.makedirs(pasta, exist_ok=True)

        self.token_inicial = None
        if os.path.exists(ficheiro):
            with open(ficheiro, "r") as f:
                self.dados = json.load(f)
            if self.dados.get("formato") != FORMATO:
                self._migrar()
        else:
            self.dados = {"formato": FORMATO, "tokens": []}
            self.token_inicial = self.criar("cli")

    # ------------------------------------------------------------------ disco
    def _guardar(self):
        tmp = self.ficheiro + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.dados, f, indent=4)
        os.replace(tmp, self.ficheiro)

    def _migrar(self):
        """Converte o formato 1 (token em claro) sem invalidar o token atual."""
        antigo = self.dados.get("token")
        self.dados = {
            "formato": FORMATO,
            "tokens": [],
            "migrado_de": self.dados.get("formato", 1),
            "migracao_em": time.ctime(),
        }
        if antigo and hmac.compare_digest(str(antigo), TOKEN_PUBLICO_CONHECIDO):
            # Token publico conhecido: migra-lo seria manter aberta a porta que
            # a correcao veio fechar. Emite-se um novo e mostra-se uma vez.
            self._guardar()
            self.token_inicial = self.criar("cli")
            return

        if antigo:
            self.dados["tokens"].append({
                "id": secrets.token_hex(4),
                "nome": "migrado",
                "hash": hash_token(antigo),
                "criado_em": "before migration",
                "nota": "token that already existed; remains valid",
            })
        self._guardar()

    # ------------------------------------------------------------------ tokens
    def criar(self, nome="token"):
        """Cria um token novo e devolve-o em claro. So esta chamada o revela."""
        token = secrets.token_hex(32)
        self.dados["tokens"].append({
            "id": secrets.token_hex(4),
            "nome": str(nome)[:40],
            "hash": hash_token(token),
            "criado_em": time.ctime(),
        })
        self._guardar()
        return token

    def validar(self, token):
        """Devolve a identidade do token (dict) ou None.

        Percorre todos os tokens para o tempo de resposta nao revelar qual
        falhou, e compara com hmac.compare_digest.
        """
        if not token:
            return None
        alvo = hash_token(token)
        encontrado = None
        for t in self.dados["tokens"]:
            if hmac.compare_digest(t["hash"], alvo):
                encontrado = t
        return encontrado

    def revogar(self, token_id):
        antes = len(self.dados["tokens"])
        self.dados["tokens"] = [t for t in self.dados["tokens"] if t["id"] != token_id]
        if len(self.dados["tokens"]) == antes:
            return False
        self._guardar()
        return True

    def regenerar(self, token_id):
        """Revoga o token e emite um novo com o mesmo nome. Devolve o novo em claro."""
        alvo = next((t for t in self.dados["tokens"] if t["id"] == token_id), None)
        if alvo is None:
            return None
        nome = alvo["nome"]
        self.revogar(token_id)
        return self.criar(nome)

    def listar(self):
        """Metadados dos tokens. Nunca inclui o resumo nem o token."""
        return [{k: v for k, v in t.items() if k != "hash"} for t in self.dados["tokens"]]

    def mostrar(self):
        print("\n[AUTH PURPLE] Configured tokens (the value is known only to whoever saved it):")
        for t in self.listar():
            print(f" - {t['id']}  {t['nome']}  created at {t['criado_em']}")
        print()
