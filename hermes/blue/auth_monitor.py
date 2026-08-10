class AuthMonitor:
    def __init__(self, router=None):
        print("[AUTH] Módulo auth_monitor iniciado.")
        self.router = router

        # Contador de falhas por IP
        self.falhas_por_ip = {}

    def login_fail(self, ip):
        """
        Regista uma tentativa de login falhada e envia evento ao pipeline.
        """

        # Atualizar contador
        if ip not in self.falhas_por_ip:
            self.falhas_por_ip[ip] = 0

        self.falhas_por_ip[ip] += 1

        falhas = self.falhas_por_ip[ip]

        print(f"[AUTH] Falha de login detectada em {ip} (falhas consecutivas: {falhas})")

        evento = {
            "tipo": "login_fail",
            "ip": ip,
            "falhas_consecutivas": falhas
        }

        # Enviar evento ao pipeline
        if self.router and self.router.alert_engine:
            self.router.alert_engine.processar_evento(evento)

        if self.router and self.router.log_manager:
            self.router.log_manager.registar_evento({
                "evento": evento,
                "alerta": False,  # alerta será decidido pelo alert_engine
                "falhas_consecutivas": falhas
            })

