#!/usr/bin/env python3
"""Hermes-Lab entry point: starts the PURPLE service and opens the dashboard."""
import shutil
import subprocess
import threading
import time
import webbrowser

from hermes.purple.purple_runner import PurpleRunner


def abrir_dashboard(url):
    """Abre o dashboard numa janela privada do Firefox.

    A janela privada NAO e por causa do token - o token deixou de ir no URL e a
    pagina autentica-se com um nonce de uso unico. E por uma razao funcional: os
    pedidos do dashboard ao localhost falham numa janela normal deste sistema, e
    o sintoma visivel sao os botoes das ferramentas (nmap, Zeek, Suricata) a
    devolver NetworkError. Numa janela privada as extensoes estao desligadas e os
    pedidos passam.

    Ou seja: mantem-se o comportamento de sempre, agora com o motivo certo
    escrito ao lado. Se o Firefox nao existir, cai para o browser por omissao.
    """
    firefox = shutil.which("firefox")
    if firefox:
        try:
            subprocess.Popen([firefox, "--private-window", url])
            return
        except Exception as e:
            print(f"[Hermes] Could not start Firefox ({e}).")
    print("[Hermes] Firefox not found, using the default browser.")
    print("[Hermes] If the tool buttons fail, open the URL in a private window.")
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
    # Entrada sem token para quem esta na maquina: nonce de uso unico no
    # fragmento do URL, trocado por uma cookie HttpOnly. O fragmento nao vai
    # para o servidor nem para os logs.
    nonce = runner.api.bootstrap.novo_nonce()
    url = f"http://127.0.0.1:{porta}/dashboard/view#n={nonce}"
    print(f"[Hermes] Dashboard: http://127.0.0.1:{porta}/dashboard/view")

    # Os tokens sao guardados apenas como resumo: o valor em claro so existe
    # no momento em que e criado. Por isso so o mostramos quando acabou de
    # nascer (primeiro arranque) - depois disso, usa o que guardaste.
    if runner.auth.token_inicial:
        print("[Hermes] Token criado agora (para outros dispositivos). Guarda-o: nao volta a ser mostrado.")
        print(f"[Hermes]   {runner.auth.token_inicial}")
    else:
        nomes = ", ".join(t["nome"] for t in runner.auth.listar()) or "(nenhum)"
        print(f"[Hermes] Tokens configurados para clientes remotos: {nomes}")

    abrir_dashboard(url)

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Hermes] Stopped.")


if __name__ == "__main__":
    main()
