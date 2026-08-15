"""
zeek_reader.py
Le o conn.log do Zeek (formato TSV com cabecalho #fields) e traduz
para o formato de evento comum do Hermes.

Segue o mesmo padrao do suricata_reader.py: ferramenta continua, o
Zeek corre por conta propria e escreve para ficheiro; o Hermes so le
(ler_uma_vez) ou acompanha (vigiar, tipo tail -f).
"""

import os
import time

from hermes.core.lab_boundary import alvo_permitido
from hermes.core.event_store import write_raw, write_clean

CONN_LOG_DEFAULT = "/opt/zeek/logs/current/conn.log"

CAMPOS_DEFAULT = [
    "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
    "proto", "service", "duration", "orig_bytes", "resp_bytes",
    "conn_state", "local_orig", "local_resp", "missed_bytes",
    "history", "orig_pkts", "orig_ip_bytes", "resp_pkts",
    "resp_ip_bytes", "tunnel_parents", "ip_proto",
]

SEVERITY_DEFAULT = "info"


def _ler_campos(caminho):
    try:
        with open(caminho, "r") as f:
            for linha in f:
                if linha.startswith("#fields"):
                    return linha.strip().split("\t")[1:]
    except OSError:
        pass
    return CAMPOS_DEFAULT


def parse_evento(linha, campos=None):
    linha = linha.rstrip("\n")
    if not linha or linha.startswith("#"):
        return None

    valores = linha.split("\t")
    campos = campos or CAMPOS_DEFAULT
    dados = dict(zip(campos, valores))

    ip_origem = dados.get("id.orig_h")
    ip_destino = dados.get("id.resp_h")

    if not (alvo_permitido(ip_origem or "") or alvo_permitido(ip_destino or "")):
        return None

    evento = {
        "tipo": "zeek_connection",
        "origem": "zeek",
        "ip": ip_origem,
        "ip_destino": ip_destino,
        "porta_origem": dados.get("id.orig_p"),
        "porta_destino": dados.get("id.resp_p"),
        "protocolo": dados.get("proto"),
        "servico": dados.get("service"),
        "duracao": dados.get("duration"),
        "estado_conexao": dados.get("conn_state"),
        "timestamp_zeek": dados.get("ts"),
    }

    try:
        raw_ref = write_raw("zeek", linha + "\n")
        write_clean(
            source="zeek",
            event_type="connection",
            severity=SEVERITY_DEFAULT,
            target=ip_destino or ip_origem or "unknown",
            data={
                "ip_origem": ip_origem,
                "ip_destino": ip_destino,
                "porta_origem": dados.get("id.orig_p"),
                "porta_destino": dados.get("id.resp_p"),
                "protocolo": dados.get("proto"),
                "servico": dados.get("service"),
                "estado_conexao": dados.get("conn_state"),
            },
            raw_ref=raw_ref,
        )
    except Exception as e:
        print(f"[ZEEK_READER] Aviso: falha ao escrever raw/clean: {e}")

    return evento


def ler_uma_vez(caminho=CONN_LOG_DEFAULT):
    eventos = []
    if not os.path.exists(caminho):
        print(f"[ZEEK_READER] Ficheiro nao encontrado: {caminho}")
        return eventos

    campos = _ler_campos(caminho)

    with open(caminho, "r") as f:
        for linha in f:
            evento = parse_evento(linha, campos)
            if evento:
                eventos.append(evento)

    return eventos


def vigiar(router, caminho=CONN_LOG_DEFAULT, intervalo=2):
    if not os.path.exists(caminho):
        print(f"[ZEEK_READER] Ficheiro nao encontrado: {caminho}")
        return

    campos = _ler_campos(caminho)
    print(f"[ZEEK_READER] A vigiar {caminho}... (Ctrl+C para parar)")

    with open(caminho, "r") as f:
        f.seek(0, os.SEEK_END)

        while True:
            linha = f.readline()
            if not linha:
                time.sleep(intervalo)
                continue

            evento = parse_evento(linha, campos)
            if not evento:
                continue

            print(f"[ZEEK_READER] Conexao: {evento['ip']} -> {evento['ip_destino']}:{evento['porta_destino']} ({evento['protocolo']})")

            if router.correlator:
                router.correlator.registar_evento(evento)
            elif router.alert_engine:
                router.alert_engine.processar_evento(evento)

            if router.log_manager:
                router.log_manager.registar_evento({
                    "evento": evento,
                    "alerta": False,
                    "origem": "zeek",
                })
