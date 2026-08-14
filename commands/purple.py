import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from hermes.purple.purple_runner import PurpleRunner
import threading

_purple_runner = None


def _get_runner():
    global _purple_runner
    if _purple_runner is None:
        _purple_runner = PurpleRunner()
    return _purple_runner


def purple_status():
    runner = _get_runner()
    resultado = runner.health_check.verificar()
    print("[PURPLE] Estado:", resultado)


def purple_start():
    """
    Corrigido: corre em primeiro plano (bloqueia até Ctrl+C), tal como
    o run_purple.py já testado — uma thread daemon dentro de um comando
    de CLI de um-só-disparo morre com o processo antes de a API arrancar.
    """
    runner = _get_runner()
    porta = runner.config.obter("api_port") or 5000
    print(f"[PURPLE] A arrancar em primeiro plano. API na porta {porta}. Ctrl+C para parar.")
    runner.iniciar()


def purple_test():
    print("[PURPLE] Comando de teste executado (estrutura base).")


def register(router):
    router.register("purple_test", purple_test)
    router.register("purple_status", purple_status)
    router.register("purple_start", purple_start)
    router.register("purple_dashboard", purple_dashboard)

def purple_dashboard():
    """
    Starts PURPLE in the background and opens the dashboard in the
    default browser automatically, with the token already filled in.
    Usage: python3 hermes_cli.py purple purple_dashboard
    Ctrl+C to stop.
    """
    import threading
    import time
    import webbrowser

    runner = _get_runner()

    thread = threading.Thread(target=runner.iniciar, daemon=True)
    thread.start()

    print("[PURPLE] Starting in the background...")
    time.sleep(2)  # give the API a moment to come up

    porta = runner.config.obter("api_port") or 5000
    token = runner.auth.auth["token"]
    url = f"http://localhost:{porta}/dashboard/view?token={token}"

    print(f"[PURPLE] Opening dashboard: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[PURPLE] Could not open the browser automatically ({e}).")
        print(f"[PURPLE] Open this URL manually: {url}")

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[PURPLE] Stopped.")
