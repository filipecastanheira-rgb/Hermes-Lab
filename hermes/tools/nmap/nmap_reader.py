"""
nmap_reader.py
Fachada do Nmap para o Hermes, seguindo o contrato comum de
ferramentas (parse_evento / ler_uma_vez / vigiar), tal como acordado
com o ChatGPT para o TShark.

Diferença de tratamento face ao Suricata: o Nmap não gera um log
contínuo — corre-se sob pedido, contra um alvo. Por isso:
- ler_uma_vez(alvo): corre um scan uma vez, devolve os eventos
- vigiar(router, alvo, intervalo): corre o scan repetidamente, de
  X em X segundos (por defeito 300 = 5 min), útil para detetar
  mudanças (uma porta nova a abrir é suspeito)

Sempre protegido pelo lab_boundary — nunca corre contra um alvo fora
do laboratório autorizado.
"""

import subprocess
import time
import xml.etree.ElementTree as ET

from hermes.core.lab_boundary import alvo_permitido


def parse_evento(dados_brutos: dict) -> dict | None:
    """
    Recebe um dict já extraído de um <port> do XML do nmap (ver
    _correr_scan) e traduz para o formato de evento comum do Hermes.
    Só portas 'open' geram evento — portas fechadas/filtradas não são
    relevantes para o BLUE.
    """
    if dados_brutos.get("estado") != "open":
        return None

    ip = dados_brutos.get("ip")
    if not alvo_permitido(ip or ""):
        return None

    return {
        "tipo": "nmap_scan",
        "origem": "nmap",
        "ip": ip,
        "ip_destino": ip,
        "porta_origem": None,
        "porta_destino": dados_brutos.get("porta"),
        "protocolo": dados_brutos.get("protocolo"),
        "assinatura": f"Porta aberta: {dados_brutos.get('porta')}/{dados_brutos.get('protocolo')} ({dados_brutos.get('servico', '?')})",
        "categoria": "Port Scan Result",
        "severidade": None,
        "timestamp_ferramenta": dados_brutos.get("timestamp"),
    }


def _correr_scan(alvo: str) -> list:
    """
    Corre 'nmap -oX -' contra o alvo, devolve a lista de dicts brutos
    (um por porta encontrada), prontos a passar a parse_evento().
    """
    if not alvo_permitido(alvo):
        print(f"[NMAP_READER] Alvo fora do laboratório autorizado, recusado: {alvo}")
        return []

    try:
        resultado = subprocess.run(
            ["nmap", "-oX", "-", alvo],
            capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        print("[NMAP_READER] 'nmap' não está instalado.")
        return []
    except subprocess.TimeoutExpired:
        print(f"[NMAP_READER] Scan a {alvo} excedeu o tempo limite.")
        return []

    if resultado.returncode != 0:
        print(f"[NMAP_READER] Erro ao correr nmap: {resultado.stderr[:200]}")
        return []

    portas_brutas = []
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        raiz = ET.fromstring(resultado.stdout)
    except ET.ParseError:
        print("[NMAP_READER] Não foi possível interpretar o XML do nmap.")
        return []

    for host in raiz.findall("host"):
        endereco_el = host.find("address")
        ip = endereco_el.get("addr") if endereco_el is not None else None

        portas_el = host.find("ports")
        if portas_el is None:
            continue

        for porta_el in portas_el.findall("port"):
            estado_el = porta_el.find("state")
            servico_el = porta_el.find("service")

            portas_brutas.append({
                "ip": ip,
                "porta": int(porta_el.get("portid")),
                "protocolo": porta_el.get("protocol"),
                "estado": estado_el.get("state") if estado_el is not None else None,
                "servico": servico_el.get("name") if servico_el is not None else None,
                "timestamp": timestamp,
            })

    return portas_brutas


def ler_uma_vez(alvo: str) -> list:
    """
    Corre um scan Nmap uma vez contra 'alvo' (IP, hostname, ou
    intervalo CIDR) e devolve os eventos já traduzidos.
    """
    brutos = _correr_scan(alvo)
    eventos = [parse_evento(b) for b in brutos]
    return [e for e in eventos if e is not None]


def vigiar(router, alvo: str, intervalo: int = 300):
    """
    Corre scans repetidos contra 'alvo', de 'intervalo' em 'intervalo'
    segundos (5 min por defeito), enviando cada evento encontrado ao
    pipeline BLUE. Ctrl+C para parar.
    """
    print(f"[NMAP_READER] A vigiar '{alvo}' a cada {intervalo}s... (Ctrl+C para parar)")

    while True:
        eventos = ler_uma_vez(alvo)
        for evento in eventos:
            print(f"[NMAP_READER] {evento['assinatura']} em {evento['ip']}")

            if router.correlator:
                router.correlator.registar_evento(evento)
            elif router.alert_engine:
                router.alert_engine.processar_evento(evento)

            if router.log_manager:
                router.log_manager.registar_evento({
                    "evento": evento,
                    "alerta": True,
                    "origem": "nmap",
                })

        time.sleep(intervalo)
