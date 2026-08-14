# blue.py
# Comandos do modo BLUE — agora ligados de verdade ao pipeline testado
# (hermes.blue / hermes.modes, vindos do bloco B).

import os
import sys

# a pasta hermes/ vive ao lado deste ficheiro (../../hermes)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hermes.modes.mode_router import ModeRouter
from hermes.blue import alert_rules
from hermes.tools.suricata import suricata_reader

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "hermes_config.json")

_router_blue = None


def _get_router():
    """
    Cria o ModeRouter do BLUE uma única vez (lazy init), e carrega as
    regras avançadas. Chamadas seguintes reutilizam a mesma instância,
    para não perder o histórico de correlação entre comandos.
    """
    global _router_blue
    if _router_blue is None:
        _router_blue = ModeRouter(CONFIG_PATH)
        _router_blue.iniciar()

        if _router_blue.alert_engine:
            _router_blue.alert_engine.adicionar_regra(alert_rules.regra_bruteforce_avancada)
            _router_blue.alert_engine.adicionar_regra(alert_rules.regra_correlacao_ip)
            _router_blue.alert_engine.adicionar_regra(alert_rules.regra_suricata_alerta)

    return _router_blue


def register(router):
    router.register("blue_test", blue_test)
    router.register("blue_scan", blue_scan)
    router.register("blue_scan_range", blue_scan_range)
    router.register("blue_suricata_test", blue_suricata_test)
    router.register("blue_suricata_watch", blue_suricata_watch)


def blue_test(*args, **kwargs):
    print("[BLUE] Comando de teste executado (estrutura base).")


def blue_scan(ip="127.0.0.1", porta="22", *args, **kwargs):
    """
    Uso: python3 hermes_cli.py blue blue_scan <ip> <porta>
    """
    r = _get_router()
    r.scanner.scan_port(ip, int(porta))


def blue_scan_range(ip="127.0.0.1", inicio="20", fim="25", *args, **kwargs):
    """
    Uso: python3 hermes_cli.py blue blue_scan_range <ip> <inicio> <fim>
    """
    r = _get_router()
    abertas = r.scanner.scan_range(ip, int(inicio), int(fim))
    print(f"[BLUE] Portas abertas encontradas: {abertas}")


def blue_suricata_test(caminho="/var/log/suricata/eve.json", *args, **kwargs):
    """
    Lê o eve.json do Suricata uma vez (do início) e processa os
    alertas encontrados através do pipeline BLUE. Útil para confirmar
    que a leitura/tradução funciona, sem ficar em loop contínuo.
    Uso: python3 hermes_cli.py blue blue_suricata_test
    """
    r = _get_router()
    eventos = suricata_reader.ler_uma_vez(caminho)
    print(f"[BLUE] {len(eventos)} alerta(s) do Suricata encontrado(s).")
    for evento in eventos:
        r.correlator.registar_evento(evento)


def blue_suricata_watch(caminho="/var/log/suricata/eve.json", *args, **kwargs):
    """
    Fica a vigiar o eve.json em contínuo (tipo tail -f) e processa
    cada novo alerta do Suricata através do pipeline BLUE, em tempo
    real. Ctrl+C para parar.
    Uso: python3 hermes_cli.py blue blue_suricata_watch
    """
    r = _get_router()
    suricata_reader.vigiar(r, caminho)
