import gzip
import json
from io import BytesIO

class PurpleCompression:
    """
    Sistema de compressão para respostas da API PURPLE.
    Suporta gzip automático.
    """

    def __init__(self, ativo=True, nivel=5):
        self.ativo = ativo
        self.nivel = nivel  # nível de compressão gzip (1-9)

    def comprimir(self, dados):
        if not self.ativo:
            return dados, False  # sem compressão

        try:
            json_bytes = json.dumps(dados).encode("utf-8")
            buffer = BytesIO()

            with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=self.nivel) as gz:
                gz.write(json_bytes)

            return buffer.getvalue(), True

        except Exception:
            # fallback: devolve sem compressão
            return dados, False

