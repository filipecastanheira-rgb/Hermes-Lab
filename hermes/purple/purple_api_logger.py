import json
import time
import os


def _mascarar(token):
    """Never write a full token to the logs: keep only the first 4 characters."""
    if not token:
        return token
    return str(token)[:4] + "..."


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
            "camada": "PURPLE_API",
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
            "token": _mascarar(token),
            "payload": payload
        })

    # ============================================================
    # Auditoria de respostas
    # ============================================================
    def log_resposta(self, endpoint, resposta):
        if isinstance(resposta, dict) and "novo_token" in resposta:
            resposta = {**resposta, "novo_token": "***"}
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
            "token": _mascarar(token)
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
    def log_token_regenerado(self):
        self._escrever("token_regenerado", {})

