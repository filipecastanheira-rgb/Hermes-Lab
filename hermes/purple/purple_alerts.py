import time
import json
import os


class PurpleAlerts:
    """
    Sistema de alertas avançados para o modo PURPLE.
    Regista alertas críticos com severidade, contexto e origem.

    Corrigido:
    - self.logger.escrever() não existia (era self.logger.info())
    - timestamp agora é epoch (time.time()), consistente com
      metrics.py e com o que o dashboard espera
    - alertas passam a ser persistidos em logs/purple_alerts.json,
      que é o ficheiro que o PurpleDashboard lê — antes não havia
      nenhum código a escrever lá, o dashboard estava sempre vazio
    """

    def __init__(self, logger, ficheiro_alertas="logs/purple_alerts.json", max_historico=200):
        self.logger = logger
        self.ficheiro_alertas = ficheiro_alertas
        self.max_historico = max_historico
        os.makedirs(os.path.dirname(ficheiro_alertas), exist_ok=True)

    def _persistir(self, alerta):
        historico = []
        if os.path.exists(self.ficheiro_alertas):
            try:
                with open(self.ficheiro_alertas, "r") as f:
                    historico = json.load(f)
            except (json.JSONDecodeError, OSError):
                historico = []

        historico.append(alerta)
        if len(historico) > self.max_historico:
            historico = historico[-self.max_historico:]

        with open(self.ficheiro_alertas, "w") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)

    def emitir_alerta(self, severidade, origem, descricao, contexto=None):
        alerta = {
            "timestamp": time.time(),
            "severidade": severidade,
            "origem": origem,
            "descricao": descricao,
            "contexto": contexto or {},
        }

        self.logger.info(
            f"ALERTA [{severidade}] — origem={origem} — descricao={descricao} — contexto={alerta['contexto']}"
        )

        print(f"\n[ALERTA PURPLE] ({severidade}) {descricao}")
        print(f" - Origem: {origem}")
        print(f" - Contexto: {alerta['contexto']}\n")

        self._persistir(alerta)

        return alerta

    def alerta_modulo_falhou(self, modulo):
        return self.emitir_alerta(
            severidade="CRITICO", origem="watchdog",
            descricao=f"Módulo '{modulo}' falhou.", contexto={"modulo": modulo},
        )

    def alerta_modulo_reiniciado(self, modulo):
        return self.emitir_alerta(
            severidade="INFO", origem="watchdog",
            descricao=f"Módulo '{modulo}' reiniciado automaticamente.", contexto={"modulo": modulo},
        )

    def alerta_evento_suspeito(self, evento):
        return self.emitir_alerta(
            severidade="ALTO", origem="correlator",
            descricao="Evento suspeito detectado.", contexto=evento,
        )
