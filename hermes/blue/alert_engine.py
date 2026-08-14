"""
alert_engine.py
Motor de regras do modo BLUE.

Corrigido: o ficheiro original tinha a classe AlertEngine definida
duas vezes (copy-paste). Fica só uma versão, a completa.
"""

class AlertEngine:
    def __init__(self):
        self.regras = []
        print("[ALERT] Módulo alert_engine iniciado.")

    def adicionar_regra(self, regra_func):
        self.regras.append(regra_func)
        print("[ALERT] Regra adicionada.")

    def processar_evento(self, evento):
        regras_disparadas = []

        for regra in self.regras:
            try:
                if regra(evento):
                    regras_disparadas.append(regra.__name__)
            except Exception as e:
                print(f"[ALERT] Erro na regra {regra.__name__}: {e}")

        if regras_disparadas:
            print(f"[ALERT] ALERTA DISPARADO pelas regras: {regras_disparadas}")
            return True

        return False
