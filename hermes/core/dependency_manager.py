"""
dependency_manager.py

Garante que as dependencias externas do Hermes (Suricata, Zeek, e
futuras) estao ativas antes do PURPLE comecar a vigiar. Em vez de as
deixar sempre ligadas via systemd (desperdicio de RAM/CPU num
hardware limitado), o Hermes verifica e arranca cada uma so quando
precisa delas.

Cada funcao usa exatamente os comandos autorizados em
/etc/sudoers.d/hermes-services - nunca comandos livres ou argumentos
variaveis, para manter o principio de menor privilegio.
"""

import subprocess


def _correr(comando):
    """Corre um comando de sistema, devolve (sucesso, output)."""
    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=30
        )
        return resultado.returncode == 0, (resultado.stdout + resultado.stderr).strip()
    except Exception as e:
        return False, str(e)


def garantir_suricata(logger=None):
    """
    Confirma que o Suricata esta ativo; arranca-o se nao estiver.
    Devolve True se ficou (ou ja estava) ativo, False caso contrario.
    """
    ativo, _ = _correr(["sudo", "/usr/bin/systemctl", "is-active", "suricata"])
    if ativo:
        if logger:
            logger.info("Suricata ja estava ativo.")
        return True

    if logger:
        logger.info("Suricata inativo - a tentar arrancar...")
    sucesso, saida = _correr(["sudo", "/usr/bin/systemctl", "start", "suricata"])
    if not sucesso:
        if logger:
            logger.error(f"Falha ao arrancar Suricata: {saida}")
        return False

    ativo, _ = _correr(["sudo", "/usr/bin/systemctl", "is-active", "suricata"])
    if ativo and logger:
        logger.info("Suricata arrancado com sucesso.")
    elif not ativo and logger:
        logger.error("Suricata nao ficou ativo apos o start.")
    return ativo


def garantir_zeek(logger=None):
    """
    Confirma que o Zeek esta ativo (via zeekctl); arranca-o se nao
    estiver (zeekctl deploy). Devolve True se ficou/ja estava ativo.
    """
    sucesso, saida = _correr(["sudo", "/opt/zeek/bin/zeekctl", "status"])
    if sucesso and "running" in saida:
        if logger:
            logger.info("Zeek ja estava ativo.")
        return True

    if logger:
        logger.info("Zeek inativo - a tentar arrancar (zeekctl deploy)...")
    sucesso, saida = _correr(["sudo", "/opt/zeek/bin/zeekctl", "deploy"])
    if not sucesso:
        if logger:
            logger.error(f"Falha ao arrancar Zeek: {saida}")
        return False

    sucesso, saida = _correr(["sudo", "/opt/zeek/bin/zeekctl", "status"])
    ativo = sucesso and "running" in saida
    if ativo and logger:
        logger.info("Zeek arrancado com sucesso.")
    elif not ativo and logger:
        logger.error("Zeek nao ficou ativo apos o deploy.")
    return ativo


def garantir_dependencias(logger=None):
    """
    Chama todas as funcoes garantir_* conhecidas. Cada falha e
    isolada - uma dependencia falhar nao impede as outras de serem
    tentadas nem o PURPLE de arrancar.
    """
    resultados = {}
    for nome, funcao in [("suricata", garantir_suricata), ("zeek", garantir_zeek)]:
        try:
            resultados[nome] = funcao(logger)
        except Exception as e:
            if logger:
                logger.error(f"Erro inesperado ao garantir '{nome}': {e}")
            resultados[nome] = False
    return resultados
