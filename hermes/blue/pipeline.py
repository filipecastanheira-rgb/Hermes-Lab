"""
pipeline.py
Carrega os módulos da camada BLUE (scanner, alert_engine, log_manager,
auth_monitor, correlator) conforme config/hermes_config.json.
Substitui o antigo ModeRouter: o Hermes já não tem modos RED/BLUE/PURPLE.
"""
import json

from hermes.blue.scanner import Scanner
from hermes.blue.alert_engine import AlertEngine
from hermes.blue.log_manager import LogManager
from hermes.blue.auth_monitor import AuthMonitor
from hermes.blue.correlator import Correlator


class BluePipeline:
    def __init__(self, config_path):
        self.config_path = config_path
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
        self.modulos_ativos = config.get("modulos", [])

    def iniciar(self):
        print(f"[BLUE] Módulos ativos: {self.modulos_ativos}")
        for modulo in self.modulos_ativos:
            self._ativar_modulo(modulo)

    def _ativar_modulo(self, modulo):
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
            print(f"[BLUE] Módulo desconhecido: {modulo}")
