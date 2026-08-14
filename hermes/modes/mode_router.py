"""
mode_router.py
Router de módulos ativos, conforme o hermes_config.json.

Corrigido:
- import do scanner aponta para o pacote (hermes.blue.scanner)
- comportamento_modo() estava fora da classe por erro de indentação
- adicionado obter_permissoes(), que os testes já assumiam existir
  (usa o ModeProfile para saber as permissões do modo atual)
"""

import json

from hermes.blue.scanner import Scanner
from hermes.blue.alert_engine import AlertEngine
from hermes.blue.log_manager import LogManager
from hermes.blue.auth_monitor import AuthMonitor
from hermes.blue.correlator import Correlator
from hermes.modes.mode_profile import ModeProfile


class ModeRouter:
    def __init__(self, config_path):
        self.config_path = config_path
        self.modo = None
        self.modulos_ativos = []

        self.scanner = None
        self.alert_engine = None
        self.log_manager = None
        self.auth_monitor = None
        self.correlator = None

        self._carregar_config()

    def _carregar_config(self):
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"[ERRO] Falha ao carregar config: {e}")
            return

        self.modo = config.get("modo", "BLUE")
        self.modulos_ativos = config.get("modulos", [])

        print(f"[OK] Modo carregado: {self.modo}")

    def iniciar(self):
        print(f"[ROUTER] Hermes a iniciar em modo: {self.modo}")
        print(f"[ROUTER] Módulos ativos: {self.modulos_ativos}")

        for modulo in self.modulos_ativos:
            self._ativar_modulo(modulo)

        self.comportamento_modo()

    def _ativar_modulo(self, modulo):
        print(f"[ROUTER] A ativar módulo: {modulo}")

        if modulo == "scanner":
            self.scanner = Scanner(router=self)
        elif modulo == "alert_engine":
            self.alert_engine = AlertEngine()
        elif modulo == "log_manager":
            self.log_manager = LogManager()
        elif modulo == "auth_monitor":
            self.auth_monitor = AuthMonitor(router=self)
        elif modulo == "correlator":
            self.correlator = Correlator(router=self)
        else:
            print(f"[ROUTER] Módulo desconhecido: {modulo}")

    def comportamento_modo(self):
        """
        Ajusta comportamento do router conforme o modo escolhido.
        (Estava fora da classe no ficheiro original — corrigido.)
        """
        if self.modo == "BLUE":
            print("[ROUTER] Modo BLUE: pipeline clássico ativado.")
        elif self.modo == "PURPLE":
            print("[ROUTER] Modo PURPLE: pipeline contínuo ativado.")
        elif self.modo == "RED":
            print("[ROUTER] Modo RED: reservado para operações ofensivas.")

    def obter_permissoes(self):
        """
        Devolve as permissões do modo atual, via ModeProfile.
        Os testes já chamavam isto, mas nunca tinha sido implementado.
        """
        perfil = ModeProfile(self.modo)
        return perfil.obter_perfil().get("permissoes", {})
