"""
suricata_reader.py
Lê alertas do eve.json do Suricata e traduz para o formato de evento
que o alert_engine/correlator do BLUE já sabem processar.

O Suricata é tratado como mais uma fonte de eventos, ao lado do
scanner.py — não altera nada no resto do pipeline BLUE.

Fase 0 (2026-08-14): além do evento interno de sempre, cada alerta
processado também é persistido em raw/ e emitido para clean/ no novo
schema Hermes acordado com o ChatGPT — sem alterar o comportamento
existente do correlator/alert_engine/log_manager.
"""

import json
import time
import os

from hermes.core.lab_boundary import alvo_permitido
from hermes.core.event_store import write_raw, write_clean

EVE_PATH_DEFAULT = "/var/log/suricata/eve.json"

# Mapeamento da severidade do Suricata (1=alta ... 3=baixa, convenção
# Emerging Threats) para a escala normalizada do Hermes. Ajustar aqui
# se o ruleset mudar de convenção.
SEVERITY_MAP = {
    1: "critical",
    2: "high",
    3: "medium",
}
SEVERITY_DEFAULT = "info"  # quando o Suricata não indica severidade


def _severidade_hermes(severidade_suricata):
    return SEVERITY_MAP.get(severidade_suricata, SEVERITY_DEFAULT)


def parse_evento(linha):
    """
    Recebe uma linha crua do eve.json. Devolve um evento no formato do
    Hermes se for um alerta, ou None se não for relevante (ex: linhas
    de estatísticas, fluxo, DNS sem alerta).

    Como efeito lateral (Fase 0), também persiste a linha em raw/ e
    emite o evento equivalente para clean/ — só quando o alerta passa
    no filtro do lab_boundary, para não poluir raw/clean com ruído
    fora de âmbito.
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

    evento = {
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

    # --- Fase 0: raw/ + clean/ (aditivo, não substitui o pipeline acima) ---
    try:
        raw_ref = write_raw("suricata", linha + "\n")
        write_clean(
            source="suricata",
            event_type="alert",
            severity=_severidade_hermes(alerta.get("severity")),
            target=ip_destino or ip_origem or "unknown",
            data={
                "ip_origem": ip_origem,
                "ip_destino": ip_destino,
                "porta_origem": dados.get("src_port"),
                "porta_destino": dados.get("dest_port"),
                "protocolo": dados.get("proto"),
                "assinatura": alerta.get("signature"),
                "categoria": alerta.get("category"),
            },
            raw_ref=raw_ref,
        )
    except Exception as e:
        # Nunca deixar a camada nova quebrar o pipeline BLUE existente.
        print(f"[SURICATA_READER] Aviso: falha ao escrever raw/clean: {e}")

    return evento


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
