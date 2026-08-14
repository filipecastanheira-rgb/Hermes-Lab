"""
agregador_ferramentas.py
Ponto único que conhece todas as ferramentas ligadas ao Hermes.

Para adicionar uma ferramenta nova: escrever o <ferramenta>_reader.py
seguindo o contrato comum (parse_evento/ler_uma_vez/vigiar), e
acrescentar UMA linha aqui. Nada mais muda.
"""

import threading

from hermes.tools.suricata import suricata_reader
from hermes.tools.nmap import nmap_reader
from hermes.tools.tshark import tshark_reader   # quando existir (fachada do TSharkTool)
# from hermes.tools.nmap import nmap_reader       # quando existir

FERRAMENTAS_REGISTADAS = {
    "suricata": suricata_reader,
    "nmap": nmap_reader,
    "tshark": tshark_reader,
    # "nmap": nmap_reader,
}


def ler_uma_vez_todas(alvos: dict) -> list:
    """
    alvos: {"suricata": "/var/log/suricata/eve.json", "tshark": "eth0", ...}
    Só corre as ferramentas cujo nome apareça em 'alvos'.
    """
    eventos = []
    for nome, modulo in FERRAMENTAS_REGISTADAS.items():
        if nome not in alvos:
            continue
        print(f"[AGREGADOR] A ler '{nome}'...")
        eventos.extend(modulo.ler_uma_vez(alvos[nome]))
    return eventos


def vigiar_todas(router, alvos: dict):
    """
    Arranca uma thread de vigilância contínua por cada ferramenta
    presente em 'alvos'. Devolve a lista de threads (para o chamador
    poder fazer join() ou monitorizar se quiser).
    """
    threads = []
    for nome, modulo in FERRAMENTAS_REGISTADAS.items():
        if nome not in alvos:
            continue
        print(f"[AGREGADOR] A vigiar '{nome}'...")
        t = threading.Thread(
            target=modulo.vigiar, args=(router, alvos[nome]), daemon=True
        )
        t.start()
        threads.append(t)
    return threads
