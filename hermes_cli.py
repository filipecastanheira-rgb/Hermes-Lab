#!/usr/bin/env python3
"""Hermes-Lab entry point: starts the PURPLE service and opens the dashboard."""
import shutil
import subprocess
import threading
import time
import webbrowser

from hermes.purple.purple_runner import PurpleRunner


def abrir_dashboard(url):
    """Open the dashboard in a Firefox private window.

    A private window avoids privacy extensions that block the dashboard's
    token-authenticated requests (see README). Falls back to the default
    browser if Firefox is not installed.
    """
    firefox = shutil.which("firefox")
    if firefox:
        try:
            subprocess.Popen([firefox, "--private-window", url])
            return
        except Exception as e:
            print(f"[Hermes] Could not start Firefox ({e}).")
    print("[Hermes] Firefox not found, using the default browser.")
    print("[Hermes] If you get a 'NetworkError', open the URL in a private window.")
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
    token = runner.auth.auth["token"]
    url = f"http://localhost:{porta}/dashboard/view?token={token}"
    print(f"[Hermes] Dashboard: {url}")
    abrir_dashboard(url)

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Hermes] Stopped.")


if __name__ == "__main__":
    main()
