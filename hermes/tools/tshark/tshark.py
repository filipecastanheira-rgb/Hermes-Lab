import json
import shutil
import subprocess


class TSharkTool:
    """
    Interface do Hermes para o TShark.

    A ferramenta:
    - verifica se o tshark existe;
    - executa uma captura;
    - pede apenas os campos necessários;
    - devolve eventos estruturados ao Hermes.
    """

    CAMPOS = [
        "frame.number",
        "frame.time_epoch",
        "ip.src",
        "ip.dst",
        "frame.protocols",
        "tcp.srcport",
        "tcp.dstport",
        "tcp.flags",
        "udp.srcport",
        "udp.dstport",
        "dns.qry.name",
        "http.host",
    ]

    def __init__(self, tshark_bin="tshark"):
        self.tshark_bin = shutil.which(tshark_bin)

        if not self.tshark_bin:
            raise RuntimeError("TShark não encontrado no sistema.")

        print(f"[TSHARK] Ferramenta disponível: {self.tshark_bin}")

    def capturar(self, interface="lo", count=10):
        """
        Captura tráfego e devolve uma lista de eventos estruturados.
        """

        comando = [
            self.tshark_bin,
            "-i", interface,
            "-c", str(count),
            "-T", "fields",
            "-E", "separator=\t",
            "-E", "occurrence=f",
        ]

        for campo in self.CAMPOS:
            comando.extend(["-e", campo])

        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            check=False,
        )

        if resultado.returncode != 0:
            raise RuntimeError(
                f"TShark terminou com erro: {resultado.stderr.strip()}"
            )

        eventos = []

        for linha in resultado.stdout.splitlines():
            valores = linha.split("\t")

            evento = {}

            for indice, campo in enumerate(self.CAMPOS):
                if indice < len(valores) and valores[indice]:
                    evento[campo] = valores[indice]

            if evento:
                eventos.append(evento)

        return eventos
