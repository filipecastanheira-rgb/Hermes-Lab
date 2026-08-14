class HealthCheck:
    """
    Verifica se os módulos essenciais do Hermes estão ativos.
    """

    def __init__(self, router):
        self.router = router

    def verificar(self):
        estado = {}

        estado["scanner"] = self.router.scanner is not None
        estado["alert_engine"] = self.router.alert_engine is not None
        estado["log_manager"] = self.router.log_manager is not None
        estado["auth_monitor"] = self.router.auth_monitor is not None
        estado["correlator"] = self.router.correlator is not None

        return estado

    def imprimir_estado(self):
        estado = self.verificar()
        print("\n[HEALTHCHECK] Estado dos módulos:")

        for modulo, ativo in estado.items():
            status = "OK" if ativo else "FALHOU"
            print(f" - {modulo}: {status}")

