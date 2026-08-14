"""
mode_loader.py
Carrega e valida o modo (BLUE/RED/PURPLE) a partir da config.

Corrigido: o ficheiro original lia a chave "mode" mas o hermes_config.json
sempre teve a chave "modo" (português) — nunca batia certo, caía sempre
em modo SAFE.
"""

import json
import os


class ModeLoader:
    def __init__(self, config_path="hermes_config.json"):
        self.config_path = config_path
        self.config = {}
        self.mode = "safe"

    def ler_config(self):
        if not os.path.exists(self.config_path):
            print(f"[ERRO] Ficheiro de configuração não encontrado: {self.config_path}")
            print("[INFO] A iniciar em modo SAFE.")
            self.mode = "safe"
            return

        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"[ERRO] Falha ao ler o ficheiro de configuração: {e}")
            print("[INFO] A iniciar em modo SAFE.")
            self.mode = "safe"
            return

        self.validar_modo()

    def validar_modo(self):
        modo = self.config.get("modo", "").lower()

        if modo in ["blue", "red", "purple"]:
            self.mode = modo
            print(f"[OK] Modo carregado: {self.mode.upper()}")
        else:
            print(f"[ERRO] Modo inválido no ficheiro: {modo}")
            print("[INFO] A iniciar em modo SAFE.")
            self.mode = "safe"

    def exportar_modo(self):
        return self.mode
