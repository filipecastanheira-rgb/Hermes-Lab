import shutil
import subprocess


class TcpdumpTool:
    """Interface do Hermes para o tcpdump."""

    def __init__(self, tcpdump_bin="tcpdump"):
        self.tcpdump_bin = shutil.which(tcpdump_bin)

        if not self.tcpdump_bin:
            raise RuntimeError("tcpdump não encontrado no sistema.")

        print(f"[TCPDUMP] Ferramenta disponível: {self.tcpdump_bin}")

    def capturar(self, interface="lo", count=10):
        """Captura pacotes numa interface e devolve a saída do tcpdump."""

        comando = [
            self.tcpdump_bin,
            "-i", interface,
            "-c", str(count),
            "-nn",
        ]

        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            check=False,
        )

        if resultado.returncode != 0:
            raise RuntimeError(
                f"tcpdump terminou com erro: {resultado.stderr.strip()}"
            )

        return resultado.stdout
