# ============================
# Regras BASE
# ============================

def regra_porta_critica_aberta(evento):
    """
    Dispara alerta quando uma porta crítica está aberta.
    """
    portas_criticas = [22, 80, 443]

    porta = evento.get("porta")
    estado = evento.get("estado")

    if porta in portas_criticas and estado == "aberta":
        return True

    return False


def regra_scan_intenso(evento):
    """
    Dispara alerta quando o evento indica scan intensivo.
    """
    if evento.get("tipo") == "scan_port":
        if evento.get("portas_abertas", 0) > 10:
            return True

    return False


def regra_ip_suspeito(evento):
    """
    Dispara alerta quando o IP está na lista de suspeitos.
    """
    ips_suspeitos = ["10.0.0.66", "192.168.1.200"]

    ip = evento.get("ip")

    if ip in ips_suspeitos:
        return True

    return False


def regra_tentativa_bruteforce(evento):
    """
    Regra base: dispara quando há uma tentativa de login falhada.
    """
    return evento.get("tipo") == "login_fail"


# ============================
# Regras AVANÇADAS (pipeline BLUE)
# ============================

def regra_scan_intensivo_consecutivo(evento):
    """
    Dispara alerta quando há vários alertas consecutivos.
    Depende do pipeline BLUE avançado.
    """
    alertas_consecutivos = evento.get("alertas_consecutivos", 0)

    LIMITE = 3

    return alertas_consecutivos >= LIMITE


def regra_bruteforce_avancada(evento):
    """
    Dispara alerta quando há várias tentativas de login falhadas consecutivas
    vindas do mesmo IP. Depende do pipeline BLUE avançado.
    """

    if evento.get("tipo") != "login_fail":
        return False

    falhas = evento.get("falhas_consecutivas", 0)

    LIMITE = 5

    return falhas >= LIMITE


def regra_correlacao_ip(evento):
    """
    Dispara alerta quando um mesmo IP gera múltiplos tipos de eventos suspeitos.
    Depende do módulo correlator.
    """

    if "ip" not in evento:
        return False

    tipos = evento.get("tipos_suspeitos_do_ip", [])

    # Se o IP já gerou 2 ou mais tipos diferentes de eventos suspeitos → alerta
    return len(set(tipos)) >= 2



def regra_suricata_alerta(evento):
    """
    Dispara sempre que o evento vier do Suricata (já passou pelo motor
    de deteção dele, por definição é relevante).
    """
    return evento.get("tipo") == "suricata_alert"
