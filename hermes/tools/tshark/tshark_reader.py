"""
tshark_reader.py
Fachada do TShark para o Hermes.
Expõe o contrato comum das ferramentas:
parse_evento / ler_uma_vez / vigiar.
O TSharkTool permanece responsável pela implementação da captura.
Esta camada apenas adapta os resultados ao formato comum do Hermes.

CORREÇÃO DE SEGURANÇA (2026-08-14): esta fachada não tinha
lab_boundary — o TShark captura por interface, não por IP, por isso
o alvo_permitido() tem de filtrar CADA pacote capturado (origem OU
destino fora do lab = descartado), em vez de bloquear a captura à
entrada como o Nmap faz.

Fase 0 (2026-08-14): eventos que passam no lab_boundary são também
persistidos em raw/ e emitidos para clean/ no schema Hermes.
"""
import time

from hermes.tools.tshark.tshark import TSharkTool
from hermes.core.lab_boundary import alvo_permitido
from hermes.core.event_store import write_raw, write_clean


def parse_evento(dados_brutos: dict) -> dict | None:
    """
    Traduz um evento bruto do TShark para o formato comum do Hermes.
    Descarta silenciosamente qualquer pacote cuja origem E destino
    estejam fora do laboratório autorizado.
    """
    if not dados_brutos:
        return None

    ip_origem = dados_brutos.get("ip.src")
    ip_destino = dados_brutos.get("ip.dst")

    if not (alvo_permitido(ip_origem or "") or alvo_permitido(ip_destino or "")):
        return None

    evento = {
        "tipo": "tshark_event",
        "origem": "tshark",
        "ip": ip_origem,
        "ip_destino": ip_destino,
        "porta_origem": dados_brutos.get("tcp.srcport") or dados_brutos.get("udp.srcport"),
        "porta_destino": dados_brutos.get("tcp.dstport") or dados_brutos.get("udp.dstport"),
        "protocolo": dados_brutos.get("frame.protocols"),
        "tcp_flags": dados_brutos.get("tcp.flags"),
        "dns_query": dados_brutos.get("dns.qry.name"),
        "http_host": dados_brutos.get("http.host"),
        "timestamp_ferramenta": dados_brutos.get("frame.time_epoch"),
        "frame_number": dados_brutos.get("frame.number"),
    }

    # --- Fase 0: raw/ + clean/ (aditivo) ---
    try:
        raw_ref = write_raw("tshark", str(dados_brutos) + "\n")
        write_clean(
            source="tshark",
            event_type="packet",
            severity="info",  # TShark não tem escala própria de gravidade
            target=ip_destino or ip_origem or "unknown",
            data={
                "ip_origem": ip_origem,
                "ip_destino": ip_destino,
                "porta_origem": evento["porta_origem"],
                "porta_destino": evento["porta_destino"],
                "protocolo": evento["protocolo"],
                "dns_query": evento["dns_query"],
                "http_host": evento["http_host"],
            },
            raw_ref=raw_ref,
        )
    except Exception as e:
        print(f"[TSHARK_READER] Aviso: falha ao escrever raw/clean: {e}")

    return evento


def ler_uma_vez(interface: str = "lo", count: int = 10) -> list:
    """
    Faz uma captura finita e devolve eventos já traduzidos (só os que
    passam no lab_boundary).
    """
    ferramenta = TSharkTool()
    brutos = ferramenta.capturar(interface, count)
    eventos = [parse_evento(evento) for evento in brutos]
    return [evento for evento in eventos if evento is not None]


def vigiar(router, interface: str = "lo", intervalo: int = 2, count: int = 10):
    """
    Faz capturas sucessivas e envia os eventos para o pipeline do Hermes.
    """
    print(
        f"[TSHARK_READER] A vigiar '{interface}' "
        f"em lotes de {count} pacotes a cada {intervalo}s..."
    )
    while True:
        eventos = ler_uma_vez(interface, count)
        for evento in eventos:
            print(f"[TSHARK_READER] Evento: {evento}")
            if router.correlator:
                router.correlator.registar_evento(evento)
            elif router.alert_engine:
                router.alert_engine.processar_evento(evento)
            if router.log_manager:
                router.log_manager.registar_evento({
                    "evento": evento,
                    "alerta": False,
                    "origem": "tshark",
                })
        time.sleep(intervalo)
