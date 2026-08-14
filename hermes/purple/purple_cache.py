import time

class PurpleCache:
    """
    Sistema de cache para a API PURPLE.
    Guarda respostas recentes para acelerar chamadas.
    """

    def __init__(self, ttl=5):
        # TTL = tempo de vida da cache (segundos)
        self.ttl = ttl
        self.cache = {}

    def _expirado(self, timestamp):
        return (time.time() - timestamp) > self.ttl

    def obter(self, chave):
        if chave not in self.cache:
            return None

        valor, timestamp = self.cache[chave]

        if self._expirado(timestamp):
            del self.cache[chave]
            return None

        return valor

    def guardar(self, chave, valor):
        self.cache[chave] = (valor, time.time())

    def limpar(self):
        expirados = []
        for chave, (_, timestamp) in self.cache.items():
            if self._expirado(timestamp):
                expirados.append(chave)

        for chave in expirados:
            del self.cache[chave]

