"""
lab_boundary.py
Único ponto de decisão sobre se um alvo de rede está dentro do
laboratório autorizado. NENHUMA ferramenta (Suricata contra alvo ao
vivo, TShark, Nmap, e mais tarde RED) corre contra um IP/rede sem
passar por aqui primeiro.

Config em config/lab_allowed.json:
  {"redes_permitidas": ["127.0.0.0/8", "192.168.100.0/24"]}
Se o ficheiro não existir, só a loopback é permitida por defeito —
seguro por omissão.
"""

import ipaddress
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "lab_allowed.json")

REDES_PERMITIDAS_DEFAULT = ["127.0.0.0/8"]


def _carregar_redes():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                dados = json.load(f)
                return dados.get("redes_permitidas", REDES_PERMITIDAS_DEFAULT)
        except (json.JSONDecodeError, OSError):
            return REDES_PERMITIDAS_DEFAULT
    return REDES_PERMITIDAS_DEFAULT


def alvo_permitido(ip_ou_rede: str) -> bool:
    """
    Devolve True só se o alvo estiver dentro de uma das redes
    permitidas. Qualquer erro de parsing (endereço inválido) resulta
    em False — falha sempre para o lado seguro.
    """
    try:
        alvo = ipaddress.ip_network(ip_ou_rede, strict=False)
    except ValueError:
        return False

    for rede_str in _carregar_redes():
        try:
            rede = ipaddress.ip_network(rede_str, strict=False)
        except ValueError:
            continue
        if alvo.version != rede.version:
            continue
        if alvo == rede or alvo.subnet_of(rede):
            return True

    return False


def adicionar_rede_permitida(rede_str: str):
    """
    Acrescenta uma rede à allowlist (ex: quando o lab de VMs tiver
    uma sub-rede fixa). Uso manual e deliberado, nunca automático.
    """
    redes = _carregar_redes()
    if rede_str not in redes:
        redes.append(rede_str)

    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"redes_permitidas": redes}, f, indent=2)

    return redes
