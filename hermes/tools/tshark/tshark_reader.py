"""
tshark_reader.py
Fachada do TShark para o Hermes.

Expõe o contrato comum das ferramentas:
parse_evento / ler_uma_vez / vigiar.

O TSharkTool permanece responsável pela implementação da captura.
Esta camada apenas adapta os resultados ao formato comum do Hermes.
"""

import time

from hermes.tools.tshark.tshark import TSharkTool


def parse_evento(dados_brutos: dict) -> dict | None:
    """
    Traduz um evento bruto do TShark para o formato comum do Hermes.
    """
    if not dados_brutos:
        return None

    return {
        "tipo": "tshark_event",
        "origem": "tshark",
        "ip": dados_brutos.get("ip.src"),
        "ip_destino": dados_brutos.get("ip.dst"),
        "porta_origem": dados_brutos.get("tcp.srcport") or dados_brutos.get("udp.srcport"),
        "porta_destino": dados_brutos.get("tcp.dstport") or dados_brutos.get("udp.dstport"),
        "protocolo": dados_brutos.get("frame.protocols"),
        "tcp_flags": dados_brutos.get("tcp.flags"),
        "dns_query": dados_brutos.get("dns.qry.name"),
        "http_host": dados_brutos.get("http.host"),
        "timestamp_ferramenta": dados_brutos.get("frame.time_epoch"),
        "frame_number": dados_brutos.get("frame.number"),
    }


def ler_uma_vez(interface: str = "lo", count: int = 10) -> list:
    """
    Faz uma captura finita e devolve eventos já traduzidos.
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
