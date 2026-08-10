# router.py
# Router interno de comandos do Hermes-Lab (versão de desenvolvimento)

class CommandRouter:
    def __init__(self):
        self.commands = {}

    def register(self, name: str, handler):
        """Regista um comando no router."""
        self.commands[name] = handler

    def execute(self, name: str, *args, **kwargs):
        """Executa um comando registado."""
        if name not in self.commands:
            print(f"[Router] Comando desconhecido: {name}")
            return

        handler = self.commands[name]
        return handler(*args, **kwargs)

