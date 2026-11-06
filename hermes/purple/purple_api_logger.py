import json
import time
import os
import hashlib


def token_ref(token):
    """Referencia estavel e nao reversivel para um token.

    O log nao pode guardar o token: um ficheiro de log com tokens em claro e
    um segredo em disco, e um log e copiado, enviado e arquivado com muito
    menos cuidado do que a configuracao. Este resumo de 12 caracteres permite
    correlacionar pedidos do mesmo token (e detetar abuso repetido) sem
    permitir reconstruir o token a partir do log.
    """
    if not token:
        return None
    return hashlib.sha256(str(token).encode()).hexdigest()[:12]


class PurpleAPILogger:
    """
    Logger estruturado em JSON para auditoria da API PURPLE.
    Regista:
    - chamadas
    - respostas
    - erros de autenticação
    - acessos negados
    - regeneração de tokens

    Os tokens nunca sao escritos em claro: aparece apenas `token_ref`, um
    resumo SHA-256 truncado (ver `token_ref()`).
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
    def log_chamada(self, endpoint, metodo, token, payload, utilizador=None):
        self._escrever("chamada", {
            "endpoint": endpoint,
            "metodo": metodo,
            "utilizador": utilizador,
            "token_ref": token_ref(token),
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
            "token_ref": token_ref(token),
            "token_presente": bool(token)
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
            "token_ref": token_ref(novo_token)
        })

