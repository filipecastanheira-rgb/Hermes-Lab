import datetime
import os

class LogManager:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir

        # Criar diretório de logs se não existir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        self.log_file = os.path.join(self.log_dir, "hermes.log")

        print("[LOG] Módulo log_manager iniciado.")
        print(f"[LOG] Ficheiro de logs: {self.log_file}")

    def _timestamp(self):
        """
        Gera timestamp no formato YYYY-MM-DD HH:MM:SS
        """
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def escrever(self, mensagem):
        """
        Escreve uma mensagem no ficheiro de logs.
        """
        try:
            with open(self.log_file, "a") as f:
                linha = f"[{self._timestamp()}] {mensagem}\n"
                f.write(linha)

            print(f"[LOG] {mensagem}")

        except Exception as e:
            print(f"[LOG] Erro ao escrever log: {e}")

    def registar_evento(self, evento):
        """
        Regista um evento estruturado no log.
        """
        try:
            linha = f"EVENTO: {evento}"
            self.escrever(linha)

        except Exception as e:
            print(f"[LOG] Erro ao registar evento: {e}")

