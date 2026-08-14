#!/usr/bin/env python3
# orchestrator.py
# Orchestrator do Hermes-Lab

from commands.router import CommandRouter
from commands import blue, red, purple, ia
from purple_client import PurpleClientDev


class HermesOrchestrator:
    def __init__(self, mode: str):
        self.mode = mode
        print(f"[Orchestrator] Modo selecionado: {self.mode}")

        self.purple_client = PurpleClientDev()
        print("[Orchestrator] Cliente PURPLE inicializado (DEV).")

        self.init_router()

    def init_router(self):
        self.router = CommandRouter()

        blue.register(self.router)
        red.register(self.router)
        purple.register(self.router)
        ia.register(self.router)

        print("[Orchestrator] Router inicializado e comandos registados.")

    def run(self, comando, *args):
        """
        Executa um comando registado no router (ex: 'blue_scan', com os
        argumentos que vieram da CLI).
        """
        print(f"[Orchestrator] A executar comando: {comando} {list(args)}")
        return self.router.execute(comando, *args)
