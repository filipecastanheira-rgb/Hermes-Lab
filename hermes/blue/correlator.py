class Correlator:
    def __init__(self, router=None):
        print("[CORRELATOR] Módulo correlator iniciado.")
        self.router = router

        # Histórico de tipos de eventos suspeitos por IP
        self.eventos_por_ip = {}

    def registar_evento(self, evento):
        """
        Atualiza o histórico de eventos suspeitos por IP
        e envia evento enriquecido ao alert_engine.
        """

        ip = evento.get("ip")
        tipo = evento.get("tipo")

        if not ip or not tipo:
            return

        # Inicializar lista se IP ainda não existe
        if ip not in self.eventos_por_ip:
            self.eventos_por_ip[ip] = []

        # Guardar tipo de evento suspeito
        self.eventos_por_ip[ip].append(tipo)

        # Criar evento enriquecido
        evento_enriquecido = {
            **evento,
            "tipos_suspeitos_do_ip": self.eventos_por_ip[ip]
        }

        # Enviar ao alert_engine
        if self.router and self.router.alert_engine:
            self.router.alert_engine.processar_evento(evento_enriquecido)

        # Registar no log_manager
        if self.router and self.router.log_manager:
            self.router.log_manager.registar_evento({
                "evento": evento_enriquecido,
                "alerta": False,
                "tipos_suspeitos_do_ip": self.eventos_por_ip[ip]
            })

