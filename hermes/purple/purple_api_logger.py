import json
import time
import os


class PurpleAPILogger:
    """
    Logger estruturado em JSON para auditoria da API PURPLE.
    Regista:
    - chamadas
    - respostas
    - erros de autenticação
    - acessos negados
    - regeneração de tokens
    """

    def __init__(self, ficheiro="logs/purple_api.log"):
        os.makedirs(os.path.dirname(ficheiro), exist_ok=True)
        self.ficheiro = ficheiro

    # ============================================================
    # Função interna para escrever JSON no ficheiro
    # ============================================================
    def _escrever(self, tipo, dados):
        evento = {
            "timestamp": time.time(),
            "tipo": tipo,
            "modo": "PURPLE_API",
            "dados": dados
        }

        linha = json.dumps(evento, ensure_ascii=False)

        with open(self.ficheiro, "a") as f:
            f.write(linha + "\n")

    # ============================================================
    # Auditoria de chamadas
    # ============================================================
    def log_chamada(self, endpoint, metodo, token, payload):
        self._escrever("chamada", {
            "endpoint": endpoint,
            "metodo": metodo,
            "token": token,
            "payload": payload
        })

    # ============================================================
    # Auditoria de respostas
    # ============================================================
    def log_resposta(self, endpoint, resposta):
        self._escrever("resposta", {
            "endpoint": endpoint,
            "resposta": resposta
        })

    # ============================================================
    # Erros de autenticação
    # ============================================================
    def log_erro_autenticacao(self, endpoint, token):
        self._escrever("erro_autenticacao", {
            "endpoint": endpoint,
            "token": token
        })

    # ============================================================
    # Acessos negados (rate limit, chave inválida, etc.)
    # ============================================================
    def log_acesso_negado(self, endpoint, motivo):
        self._escrever("acesso_negado", {
            "endpoint": endpoint,
            "motivo": motivo
        })

    # ============================================================
    # Regeneração de tokens
    # ============================================================
    def log_token_regenerado(self, novo_token):
        self._escrever("token_regenerado", {
            "novo_token": novo_token
        })

