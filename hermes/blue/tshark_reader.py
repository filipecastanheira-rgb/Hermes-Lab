"""
tshark_reader.py
Adaptador do TShark para o pipeline BLUE do Hermes.

Nesta primeira fase implementa apenas a tradução de um
registo bruto TShark para o formato comum de evento.
"""

from typing import Optional

from hermes.core.lab_boundary import alvo_permitido


def parse_evento(dados_brutos) -> Optional[dict]:
    """
    Traduz um registo bruto do TShark para o formato comum do Hermes.

    Recebe um dicionário correspondente a um pacote/registo TShark.
    Devolve None se não houver informação IP útil.
    """

    if not isinstance(dados_brutos, dict):
        return None

    # TShark -T json coloca normalmente os dados dentro de "_source.layers".
    layers = dados_brutos.get("_source", {}).get("layers", {})

    if not layers:
        # Permite também testar diretamente com um dicionário de layers.
        layers = dados_brutos.get("layers", dados_brutos)

    ip = layers.get("ip", {})
    tcp = layers.get("tcp", {})
    udp = layers.get("udp", {})
    frame = layers.get("frame", {})

    ip_origem = ip.get("ip.src")
    ip_destino = ip.get("ip.dst")

    # Sem endereços IP não temos ainda um evento útil para o Hermes.
    if not ip_origem and not ip_destino:
        return None

    # A fronteira do laboratório é obrigatória antes de aceitar o evento.
    if not (alvo_permitido(ip_origem or "") or alvo_permitido(ip_destino or "")):
        return None

    protocolo = None
    porta_origem = None
    porta_destino = None

    if tcp:
        protocolo = "TCP"
        porta_origem = tcp.get("tcp.srcport")
        porta_destino = tcp.get("tcp.dstport")
    elif udp:
        protocolo = "UDP"
        porta_origem = udp.get("udp.srcport")
        porta_destino = udp.get("udp.dstport")

    return {
        "tipo": "tshark_evento",
        "origem": "tshark",
        "ip": ip_origem,
        "ip_destino": ip_destino,
        "porta_origem": porta_origem,
        "porta_destino": porta_destino,
        "protocolo": protocolo,
        "assinatura": frame.get("frame.protocols"),
        "severidade": None,
        "timestamp_ferramenta": frame.get("frame.time_epoch"),
    }
