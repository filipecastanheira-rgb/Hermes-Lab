"""
openvas_reader.py
Fachada do OpenVAS/Greenbone para o Hermes, seguindo o contrato comum
de ferramentas (parse_evento / ler_uma_vez / vigiar), tal como
nmap_reader.py e tshark_reader.py.

Diferenca fundamental face ao Nmap: o OpenVAS fala GMP (Greenbone
Management Protocol), nao e um binario local. O acesso e feito via
`docker-compose run --rm gvm-tools gvm-cli ... socket --xml ...`,
exatamente o fluxo ja validado manualmente (create_target ->
create_task -> start_task -> get_reports). Este modulo automatiza
esse fluxo, com deteccao/reaproveitamento de target e task existentes,
e faz polling ate o scan terminar (ou expirar o tempo limite).

AVISO DE ARQUITETURA (nao escondido, decisao a rever):
Um scan OpenVAS pode demorar varios minutos - o `ler_uma_vez()` deste
modulo e SINCRONO e BLOQUEANTE ate o scan terminar (ou ate
MAX_ESPERA_SEGUNDOS). Se a IA decidir correr OpenVAS a partir do loop
periodico de decide_action() (que corre de 5 em 5 min), essa chamada
pode bloquear o loop por mais tempo que o proprio intervalo. Fica
aceite por agora, na mesma logica de "ferramentas on-demand simples e
sincronas" ja usada para nmap/tshark - mas e um ponto a re-avaliar se
o OpenVAS comecar a ser chamado com frequencia pela IA autonoma.

Sempre protegido pelo lab_boundary - o alvo passa por
alvo_permitido() antes de qualquer chamada GMP, tal como acontece com
o nmap.
"""

import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET

from hermes.core.lab_boundary import alvo_permitido
from hermes.core.event_store import write_raw, write_clean
from hermes.core.credentials import credentials


GREENBONE_DIR = "/mnt/hermes-data/backup-ubuntu/greenbone-community-edition"
CONFIG_ID_FULL_AND_FAST = "daba56c8-73ec-11df-a475-002264764cea"
SCANNER_ID_OPENVAS_DEFAULT = "08b69003-5fc2-4037-a479-93b440211c73"
PORT_LIST_ID_DEFAULT = "730ef368-57e2-11e1-a90f-406186ea4fc5"
REPORT_FORMAT_ID_XML = "a994b278-1f62-11e1-96ac-406186ea4fc5"

MAX_ESPERA_SEGUNDOS = 600
INTERVALO_POLL_SEGUNDOS = 15


def _gmp(xml_command, timeout=60):
    """
    Corre um comando GMP via gvm-cli dentro do container gvm-tools,
    tal como o fluxo ja validado manualmente. Devolve
    (elemento_xml_raiz, texto_bruto_stdout). Em caso de falha,
    devolve (None, "").
    """
    conta = credentials.get("gvm_hermes")
    usuario, password = conta["username"], conta["password"]
    cmd = [
        "docker-compose", "run", "--rm", "gvm-tools",
        "gvm-cli", "--gmp-username", usuario, "--gmp-password", password,
        "socket", "--xml", xml_command,
    ]
    try:
        resultado = subprocess.run(
            cmd, cwd=GREENBONE_DIR, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        print("[OPENVAS_READER] 'docker-compose' nao encontrado.")
        return None, ""
    except subprocess.TimeoutExpired:
        print("[OPENVAS_READER] Comando GMP excedeu o tempo limite: " + xml_command[:80])
        return None, ""

    if resultado.returncode != 0:
        print("[OPENVAS_READER] Erro GMP: " + resultado.stderr[:300])
        return None, ""

    stdout = resultado.stdout.strip()
    try:
        raiz = ET.fromstring(stdout)
    except ET.ParseError:
        print("[OPENVAS_READER] Nao foi possivel interpretar resposta GMP.")
        return None, stdout
    return raiz, stdout


def _obter_ou_criar_target(alvo):
    nome_target = "hermes-" + alvo
    raiz, _ = _gmp("<get_targets filter='name=" + nome_target + "'/>")
    if raiz is not None:
        existente = raiz.find(".//target")
        if existente is not None:
            return existente.get("id")

    raiz, _ = _gmp(
        "<create_target><name>" + nome_target + "</name><hosts>" + alvo + "</hosts>"
        "<port_list id='" + PORT_LIST_ID_DEFAULT + "'/></create_target>"
    )
    return raiz.get("id") if raiz is not None else None


def _obter_ou_criar_task(target_id, alvo):
    nome_task = "hermes-scan-" + alvo
    raiz, _ = _gmp("<get_tasks filter='name=" + nome_task + "'/>")
    if raiz is not None:
        existente = raiz.find(".//task")
        if existente is not None:
            return existente.get("id")

    raiz, _ = _gmp(
        "<create_task><name>" + nome_task + "</name>"
        "<target id='" + target_id + "'/>"
        "<config id='" + CONFIG_ID_FULL_AND_FAST + "'/>"
        "<scanner id='" + SCANNER_ID_OPENVAS_DEFAULT + "'/></create_task>"
    )
    return raiz.get("id") if raiz is not None else None


def _iniciar_e_esperar(task_id):
    raiz, _ = _gmp("<start_task task_id='" + task_id + "'/>")
    if raiz is None:
        return None

    esperado = 0
    while esperado < MAX_ESPERA_SEGUNDOS:
        raiz, _ = _gmp("<get_tasks task_id='" + task_id + "'/>")
        if raiz is not None:
            status_el = raiz.find(".//status")
            if status_el is not None and status_el.text == "Done":
                report_el = raiz.find(".//last_report/report")
                if report_el is not None:
                    return report_el.get("id")
        time.sleep(INTERVALO_POLL_SEGUNDOS)
        esperado += INTERVALO_POLL_SEGUNDOS

    print("[OPENVAS_READER] Scan nao terminou dentro do tempo limite (" + str(MAX_ESPERA_SEGUNDOS) + "s).")
    return None


def _parse_report_xml(xml_texto):
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        raiz = ET.fromstring(xml_texto)
    except ET.ParseError:
        print("[OPENVAS_READER] Nao foi possivel interpretar o XML do relatorio.")
        return []

    resultados_brutos = []
    for result_el in raiz.findall(".//result"):
        nome_el = result_el.find("name")
        host_el = result_el.find("host")
        port_el = result_el.find("port")
        threat_el = result_el.find("threat")
        severity_el = result_el.find("severity")
        nvt_el = result_el.find("nvt")
        descricao_el = result_el.find("description")

        try:
            severidade_cvss = float(severity_el.text) if severity_el is not None and severity_el.text else 0.0
        except ValueError:
            severidade_cvss = 0.0

        resultados_brutos.append({
            "nome": nome_el.text if nome_el is not None else "Resultado OpenVAS",
            "host": host_el.text if host_el is not None else None,
            "porta": port_el.text if port_el is not None else None,
            "ameaca": threat_el.text if threat_el is not None else "Log",
            "severidade_cvss": severidade_cvss,
            "nvt_oid": nvt_el.get("oid") if nvt_el is not None else None,
            "descricao": descricao_el.text if descricao_el is not None else None,
            "timestamp": timestamp,
        })
    return resultados_brutos


def _mapear_severidade(cvss):
    if cvss >= 9.0:
        return "critical"
    if cvss >= 7.0:
        return "high"
    if cvss >= 4.0:
        return "medium"
    if cvss >= 0.1:
        return "low"
    return "info"


def parse_evento(dados_brutos):
    """
    Recebe um dict ja extraido de um <result> do relatorio GMP (ver
    _parse_report_xml) e traduz para o formato de evento comum do
    Hermes. Ao contrario do nmap (so portas 'open'), aqui TODOS os
    resultados sao guardados, incluindo os de severidade 'Log' -
    num scan de vulnerabilidades, ate um resultado informativo pode
    ser relevante para correlacao futura.
    """
    host = dados_brutos.get("host")
    if not alvo_permitido(host or ""):
        return None

    severidade = _mapear_severidade(dados_brutos.get("severidade_cvss", 0.0))

    evento = {
        "tipo": "openvas_scan",
        "origem": "openvas",
        "ip": host,
        "ip_destino": host,
        "porta_origem": None,
        "porta_destino": dados_brutos.get("porta"),
        "protocolo": None,
        "assinatura": dados_brutos.get("nome") or "Resultado OpenVAS",
        "categoria": "Vulnerability Scan Result",
        "severidade": severidade,
        "timestamp_ferramenta": dados_brutos.get("timestamp"),
    }

    raw_ref = dados_brutos.get("_raw_ref")
    try:
        write_clean(
            source="openvas",
            event_type="vulnerability_found",
            severity=severidade,
            target=host or "unknown",
            data={
                "nome": dados_brutos.get("nome"),
                "porta": dados_brutos.get("porta"),
                "ameaca_gmp": dados_brutos.get("ameaca"),
                "severidade_cvss": dados_brutos.get("severidade_cvss"),
                "nvt_oid": dados_brutos.get("nvt_oid"),
                "descricao": (dados_brutos.get("descricao") or "")[:500],
            },
            raw_ref=raw_ref,
        )
    except Exception as e:
        print("[OPENVAS_READER] Aviso: falha ao escrever clean/: " + str(e))

    return evento


def ler_uma_vez(alvo):
    """
    Corre o fluxo GMP completo contra 'alvo' (get/create target ->
    get/create task -> start_task -> polling ate 'Done' -> get_reports)
    e devolve os eventos ja traduzidos. Bloqueante ate o scan terminar
    ou ate MAX_ESPERA_SEGUNDOS (ver aviso de arquitetura no topo do
    ficheiro).
    """
    if not alvo_permitido(alvo):
        print("[OPENVAS_READER] Alvo fora do laboratorio autorizado, recusado: " + alvo)
        return []

    target_id = _obter_ou_criar_target(alvo)
    if not target_id:
        print("[OPENVAS_READER] Falha ao obter/criar target.")
        return []

    task_id = _obter_ou_criar_task(target_id, alvo)
    if not task_id:
        print("[OPENVAS_READER] Falha ao obter/criar task.")
        return []

    report_id = _iniciar_e_esperar(task_id)
    if not report_id:
        print("[OPENVAS_READER] Scan nao produziu relatorio (timeout ou falha).")
        return []

    _, xml_bruto = _gmp("<get_reports report_id='" + report_id + "' format_id='" + REPORT_FORMAT_ID_XML + "' details='1' filter='apply_overrides=0 min_qod=0 rows=1000'/>")
    if not xml_bruto:
        return []

    raw_ref = None
    try:
        raw_ref = write_raw("openvas", xml_bruto, extension="xml")
    except Exception as e:
        print("[OPENVAS_READER] Aviso: falha ao escrever raw/: " + str(e))

    brutos = _parse_report_xml(xml_bruto)
    for b in brutos:
        b["_raw_ref"] = raw_ref

    eventos = [parse_evento(b) for b in brutos]
    return [e for e in eventos if e is not None]


def vigiar(router, alvo, intervalo=3600):
    """
    Corre scans OpenVAS repetidos contra 'alvo'. Intervalo por
    defeito de 1h (bem mais longo que o nmap/tshark) porque um scan
    de vulnerabilidades e pesado em CPU - nao faz sentido correr de
    5 em 5 min no hardware constrangido do lab. Ctrl+C para parar.
    """
    print("[OPENVAS_READER] A vigiar '" + alvo + "' a cada " + str(intervalo) + "s... (Ctrl+C para parar)")

    while True:
        eventos = ler_uma_vez(alvo)
        for evento in eventos:
            print("[OPENVAS_READER] " + evento["assinatura"] + " em " + str(evento["ip"]) + " (severidade: " + str(evento["severidade"]) + ")")

            if router.correlator:
                router.correlator.registar_evento(evento)
            elif router.alert_engine:
                router.alert_engine.processar_evento(evento)

            if router.log_manager:
                router.log_manager.registar_evento({
                    "evento": evento,
                    "alerta": True,
                    "origem": "openvas",
                })

        time.sleep(intervalo)
