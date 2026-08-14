"""
purple_watchdog.py
Watchdog do modo PURPLE.

Corrigido: o purple_runner.py original chamava self.watchdog.recuperar(),
mas o único watchdog.py que existia (do BLUE) só tem
verificar_e_reparar(). Esta classe implementa o método certo.

Nota honesta: por agora só regista o problema e alerta — a recuperação
automática real (ex: reiniciar a thread da API) fica para quando
tiveres o núcleo estável em produção. Devolver False aqui é
intencional: não finjas uma recuperação que não aconteceu.
"""


class PurpleWatchdog:
    def __init__(self, logger):
        self.logger = logger

    def recuperar(self, estado):
        componentes_falhados = [k for k, v in estado.items() if k != "ok" and not v]

        if not componentes_falhados:
            return False

        self.logger.error("Watchdog: componentes falhados detetados.", extra={"componentes": componentes_falhados})

        for componente in componentes_falhados:
            if componente == "api_thread_viva":
                self.logger.warn("Watchdog: thread da API PURPLE morreu. Recuperação automática ainda não implementada — precisa de reinício manual.")
            else:
                self.logger.warn(f"Watchdog: componente '{componente}' em falha. Recuperação automática ainda não implementada.")

        # Recuperação automática real é o próximo passo, não finjas sucesso agora
        return False
