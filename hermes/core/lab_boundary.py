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
import re

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "lab_allowed.json")

REDES_PERMITIDAS_DEFAULT = ["127.0.0.0/8"]

# One /24. A target can be inside the lab and still too large to scan.
MAX_ENDERECOS_ALVO = 256


def _carregar_redes():
    """Return a fresh list of allowed networks.

    Always a copy, so callers can never change the built-in default. A file
    whose structure is not the expected one falls back to the default, and
    entries that are not strings are ignored.
    """
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                dados = json.load(f)
        except (ValueError, OSError):
            return list(REDES_PERMITIDAS_DEFAULT)
        if not isinstance(dados, dict):
            return list(REDES_PERMITIDAS_DEFAULT)
        redes = dados.get("redes_permitidas", REDES_PERMITIDAS_DEFAULT)
        if not isinstance(redes, list):
            return list(REDES_PERMITIDAS_DEFAULT)
        return [r for r in redes if isinstance(r, str)]
    return list(REDES_PERMITIDAS_DEFAULT)


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


def alvo_dentro_do_limite(ip_ou_rede, max_enderecos=MAX_ENDERECOS_ALVO) -> bool:
    """
    True only if the target is a valid address or network with at most
    max_enderecos addresses. This is about size, not about membership of
    the lab: it is checked together with alvo_permitido(). Anything that
    is not a valid target string is refused.
    """
    if not isinstance(ip_ou_rede, str):
        return False
    try:
        alvo = ipaddress.ip_network(ip_ou_rede, strict=False)
    except ValueError:
        return False
    return alvo.num_addresses <= max_enderecos


def interface_valida(nome) -> bool:
    """
    True only if nome looks like a Linux network interface name: up to 15
    characters, letters, digits, dot, underscore or hyphen, and not starting
    with a hyphen. A capture target that is anything else (a path, a URL, an
    option, text with spaces or shell characters) is refused before tshark runs.
    """
    return isinstance(nome, str) and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,14}", nome) is not None


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
