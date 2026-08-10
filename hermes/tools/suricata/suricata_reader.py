"""
suricata_reader.py
Lê alertas do eve.json do Suricata e traduz para o formato de evento
que o alert_engine/correlator do BLUE já sabem processar.

O Suricata é tratado como mais uma fonte de eventos, ao lado do
scanner.py — não altera nada no resto do pipeline BLUE.
"""

import json
import time
import os

from hermes.core.lab_boundary import alvo_permitido

EVE_PATH_DEFAULT = "/var/log/suricata/eve.json"


def parse_evento(linha):
    """
    Recebe uma linha crua do eve.json. Devolve um evento no formato do
    Hermes se for um alerta, ou None se não for relevante (ex: linhas
    de estatísticas, fluxo, DNS sem alerta).
    """
    linha = linha.strip()
    if not linha:
        return None

    try:
        dados = json.loads(linha)
    except json.JSONDecodeError:
        return None

    if dados.get("event_type") != "alert":
        return None

    alerta = dados.get("alert", {})

    ip_origem = dados.get("src_ip")
    ip_destino = dados.get("dest_ip")

    # Fronteira de segurança: só processamos eventos cujo IP de origem
    # ou destino esteja dentro do laboratório autorizado. Protege
    # contra processar tráfego real caso o Suricata seja apontado, por
    # engano, para uma interface fora do lab.
    if not (alvo_permitido(ip_origem or "") or alvo_permitido(ip_destino or "")):
        return None

    return {
        "tipo": "suricata_alert",
        "origem": "suricata",
        "ip": ip_origem,
        "ip_destino": ip_destino,
        "porta_origem": dados.get("src_port"),
        "porta_destino": dados.get("dest_port"),
        "protocolo": dados.get("proto"),
        "assinatura": alerta.get("signature"),
        "categoria": alerta.get("category"),
        "severidade": alerta.get("severity"),
        "timestamp_suricata": dados.get("timestamp"),
    }


def ler_uma_vez(caminho=EVE_PATH_DEFAULT):
    """
    Lê o ficheiro inteiro (do início) e devolve uma lista de eventos de
    alerta já traduzidos. Útil para testes/leitura pontual.
    """
    eventos = []
    if not os.path.exists(caminho):
        print(f"[SURICATA_READER] Ficheiro não encontrado: {caminho}")
        return eventos

    with open(caminho, "r") as f:
        for linha in f:
            evento = parse_evento(linha)
            if evento:
                eventos.append(evento)

    return eventos


def vigiar(router, caminho=EVE_PATH_DEFAULT, intervalo=2):
    """
    Fica a "seguir" o eve.json (tipo tail -f), e para cada novo alerta
    que aparecer, envia ao alert_engine/correlator/log_manager do
    router BLUE já existente — igual ao que o scanner.py faz.
    """
    if not os.path.exists(caminho):
        print(f"[SURICATA_READER] Ficheiro não encontrado: {caminho}")
        return

    print(f"[SURICATA_READER] A vigiar {caminho}... (Ctrl+C para parar)")

    with open(caminho, "r") as f:
        f.seek(0, os.SEEK_END)  # só eventos novos a partir de agora

        while True:
            linha = f.readline()
            if not linha:
                time.sleep(intervalo)
                continue

            evento = parse_evento(linha)
            if not evento:
                continue

            print(f"[SURICATA_READER] Alerta: {evento['assinatura']} ({evento['ip']} -> {evento['ip_destino']})")

            if router.correlator:
                router.correlator.registar_evento(evento)
            elif router.alert_engine:
                router.alert_engine.processar_evento(evento)

            if router.log_manager:
                router.log_manager.registar_evento({
                    "evento": evento,
                    "alerta": True,
                    "origem": "suricata",
                })
