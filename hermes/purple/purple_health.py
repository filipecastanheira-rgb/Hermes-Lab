"""
purple_health.py
Health-check do modo PURPLE.

Corrigido: o purple_runner.py original reaproveitava o health_check.py
do BLUE, que espera um objeto "router" com atributos .scanner,
.alert_engine, etc. Passava-lhe o logger por engano — rebentava sempre
na primeira iteração do loop (AttributeError). Esta classe verifica os
componentes que o PURPLE realmente tem.
"""


class PurpleHealthCheck:
    def __init__(self, runner):
        """
        runner: a instância de PurpleRunner, para inspecionar os seus
        componentes (config, cache, auth, etc.)
        """
        self.runner = runner

    def verificar(self):
        estado = {
            "config": self.runner.config is not None,
            "auth": self.runner.auth is not None,
            "cache": self.runner.cache is not None,
            "metrics": self.runner.metrics is not None,
            "webhooks": self.runner.webhooks is not None,
            "api_thread_viva": self.runner._api_thread.is_alive() if self.runner._api_thread else False,
        }
        estado["ok"] = all(estado.values())
        return estado
