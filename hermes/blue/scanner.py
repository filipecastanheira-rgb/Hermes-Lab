"""
scanner.py
Módulo de scanning do BLUE.

Corrigido: adicionado scan_range(), que os testes já assumiam existir
mas nunca tinha sido implementado.
"""

import socket


class Scanner:
    def __init__(self, router=None):
        print("[SCANNER] Módulo iniciado.")
        self.router = router
        self.alertas_consecutivos = 0

    def scan_port(self, ip, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)

        try:
            result = sock.connect_ex((ip, port))
        except Exception as e:
            print(f"[SCANNER] Erro ao conectar: {e}")
            return
        finally:
            sock.close()

        estado = "aberta" if result == 0 else "fechada"
        print(f"[SCANNER] Porta {port} {estado} em {ip}")

        evento = {
            "tipo": "scan_port",
            "ip": ip,
            "porta": port,
            "estado": estado,
        }
        self._emitir_evento(evento)

    def scan_range(self, ip, porta_inicio, porta_fim):
        """
        Faz scan a um intervalo de portas. Devolve a lista de portas
        encontradas abertas.
        """
        abertas = []
        for porta in range(porta_inicio, porta_fim + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            try:
                result = sock.connect_ex((ip, porta))
            except Exception as e:
                print(f"[SCANNER] Erro ao conectar na porta {porta}: {e}")
                continue
            finally:
                sock.close()

            if result == 0:
                abertas.append(porta)
                print(f"[SCANNER] Porta {porta} aberta em {ip}")

        evento = {
            "tipo": "scan_range",
            "ip": ip,
            "porta_inicio": porta_inicio,
            "porta_fim": porta_fim,
            "portas_abertas": abertas,
        }
        self._emitir_evento(evento)
        return abertas

    def _emitir_evento(self, evento):
        if not self.router:
            return

        if self.router.alert_engine:
            alerta = self.router.alert_engine.processar_evento(evento)
        else:
            alerta = False

        if alerta:
            self.alertas_consecutivos += 1
        else:
            self.alertas_consecutivos = 0

        evento_enriquecido = {**evento, "alertas_consecutivos": self.alertas_consecutivos}

        if self.router.alert_engine:
            self.router.alert_engine.processar_evento(evento_enriquecido)

        if self.router.log_manager:
            self.router.log_manager.registar_evento({
                "evento": evento_enriquecido,
                "alerta": alerta,
                "alertas_consecutivos": self.alertas_consecutivos,
            })
