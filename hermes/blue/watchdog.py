class Watchdog:
    """
    Watchdog interno do Hermes.
    Verifica módulos e tenta reiniciar automaticamente se falharem.
    """

    def __init__(self, router):
        self.router = router

    def verificar_e_reparar(self, estado):
        for modulo, ativo in estado.items():
            if not ativo:
                print(f"[WATCHDOG] Falha detetada no módulo: {modulo}")
                self.reiniciar_modulo(modulo)

    def reiniciar_modulo(self, modulo):
        print(f"[WATCHDOG] A tentar reiniciar módulo: {modulo}")

        try:
            if modulo == "scanner":
                from scanner import Scanner
                self.router.scanner = Scanner(router=self.router)

            elif modulo == "alert_engine":
                from alert_engine import AlertEngine
                self.router.alert_engine = AlertEngine()

            elif modulo == "log_manager":
                from log_manager import LogManager
                self.router.log_manager = LogManager()

            elif modulo == "auth_monitor":
                from auth_monitor import AuthMonitor
                self.router.auth_monitor = AuthMonitor(router=self.router)

            elif modulo == "correlator":
                from correlator import Correlator
                self.router.correlator = Correlator(router=self.router)

            print(f"[WATCHDOG] Módulo {modulo} reiniciado com sucesso.")

        except Exception as e:
            print(f"[WATCHDOG] ERRO ao reiniciar módulo {modulo}: {e}")

