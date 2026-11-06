#!/usr/bin/env python3
"""Hermes-Lab entry point: starts the PURPLE service and opens the dashboard."""
import threading
import time
import webbrowser

from hermes.purple.purple_runner import PurpleRunner


def abrir_dashboard(url):
    """Open the dashboard in the default browser.

    The page is served without a token and asks for it on load, so a normal
    browser window works: there is no token in the URL and no header needed for
    the initial navigation (that was the reason a private window used to be
    necessary). Falls back silently if no browser can be started.
    """
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[Hermes] Could not open the browser ({e}). Open the URL manually.")


def main():
    runner = PurpleRunner()
    thread = threading.Thread(target=runner.iniciar, daemon=True)
    thread.start()
    print("[Hermes] Starting...")
    time.sleep(2)

    porta = runner.config.obter("api_port") or 5000
    url = f"http://localhost:{porta}/dashboard/view"
    print(f"[Hermes] Dashboard: {url}")

    # Os tokens sao guardados apenas como resumo: o valor em claro so existe
    # no momento em que e criado. Por isso so o mostramos quando acabou de
    # nascer (primeiro arranque) - depois disso, usa o que guardaste.
    if runner.auth.token_inicial:
        print("[Hermes] Token criado agora. Guarda-o: nao volta a ser mostrado.")
        print(f"[Hermes]   {runner.auth.token_inicial}")
    else:
        nomes = ", ".join(t["nome"] for t in runner.auth.listar()) or "(nenhum)"
        print(f"[Hermes] Tokens configurados: {nomes}")
        print("[Hermes] Usa o token que guardaste. Para emitir outro: POST /token/regenerar.")

    abrir_dashboard(url)

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Hermes] Stopped.")


if __name__ == "__main__":
    main()
