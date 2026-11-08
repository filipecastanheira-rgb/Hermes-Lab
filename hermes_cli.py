#!/usr/bin/env python3
"""Hermes-Lab entry point: starts the PURPLE service and opens the dashboard."""
import shutil
import sys
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


def comandos_tokens(argv):
    """python3 hermes_cli.py tokens {criar,listar,revogar} ..."""
    from hermes.purple import purple_tokens as T
    from hermes.purple.purple_auth import PurpleAuth

    if not argv:
        print(T.utilizacao())
        return 0

    store = PurpleAuth()
    acao = argv[0]

    if acao == "criar":
        token_id, token = T.criar(store, argv[1] if len(argv) > 1 else "token")
        print(f"Token {token_id} created. Save it: it will not be shown again.")
        print(token)
    elif acao == "listar":
        print(T.formatar_lista(T.listar(store)))
    elif acao == "revogar" and len(argv) > 1:
        print("Revoked." if T.revogar(store, argv[1]) else "Not found.")
    else:
        print(T.utilizacao())
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "tokens":
        sys.exit(comandos_tokens(sys.argv[2:]))

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
        print("[Hermes] Token created now (for other devices). Save it: it will not be shown again.")
        print(f"[Hermes]   {runner.auth.token_inicial}")
    else:
        nomes = ", ".join(t["nome"] for t in runner.auth.listar()) or "(nenhum)"
        print(f"[Hermes] Tokens configured for remote clients: {nomes}")

    abrir_dashboard(url)

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Hermes] Stopped.")


if __name__ == "__main__":
    main()
