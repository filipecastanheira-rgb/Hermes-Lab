import json
import time
import os
import hashlib
import threading


def token_ref(token):
    """Referencia estavel e nao reversivel para um token.

    O log nao pode guardar o token: um ficheiro de log com tokens em claro e
    um segredo em disco, e um log e copiado, enviado e arquivado com muito
    menos cuidado do que a configuracao. Este resumo de 12 caracteres permite
    correlacionar pedidos do mesmo token (e detetar abuso repetido) sem
    permitir reconstruir o token a partir do log.

    O prefixo "log:" evita que este valor seja um prefixo do resumo guardado em
    purple_auth.json: os dois podem ser comparados, mas nenhum se deriva do outro
    lendo um ficheiro de log.
    """
    if not token:
        return None
    return hashlib.sha256(("log:" + str(token)).encode()).hexdigest()[:12]


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

    def __init__(self, ficheiro="logs/purple_api.log", max_bytes=5 * 1024 * 1024):
        os.makedirs(os.path.dirname(ficheiro), exist_ok=True)
        self.ficheiro = ficheiro
        self.max_bytes = max_bytes
        self._trava = threading.Lock()

    def _rodar_se_preciso(self, extra):
        """Move the log to <file>.1 when the next line would pass the limit.
        Only one previous copy is kept, so the log never passes twice the limit."""
        try:
            tamanho = os.path.getsize(self.ficheiro)
        except OSError:
            return
        if tamanho > 0 and tamanho + extra > self.max_bytes:
            os.replace(self.ficheiro, self.ficheiro + ".1")
            os.chmod(self.ficheiro + ".1", 0o600)

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

        dados_linha = (linha + "\n").encode("utf-8")
        with self._trava:
            self._rodar_se_preciso(len(dados_linha))
            fd = os.open(self.ficheiro, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.fchmod(fd, 0o600)
                os.write(fd, dados_linha)
            finally:
                os.close(fd)

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
        # Only the endpoint and the size of the body are kept: the body holds real
        # events and the dashboard poll repeats it every few seconds. The events
        # themselves are stored once, in runtime/raw, which has a retention.
        tamanho = len(json.dumps(resposta, ensure_ascii=False, default=str).encode("utf-8"))
        self._escrever("resposta", {
            "endpoint": endpoint,
            "bytes": tamanho
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

