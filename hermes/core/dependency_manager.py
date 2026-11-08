"""
dependency_manager.py
Garante que as dependencias externas do Hermes (Suricata, Zeek,
OpenVAS/Greenbone, e futuras) estao ativas antes do PURPLE comecar a
vigiar. Em vez de as deixar sempre ligadas via systemd (desperdicio
de RAM/CPU num hardware limitado), o Hermes verifica e arranca cada
uma so quando precisa delas.
Cada funcao usa exatamente os comandos autorizados em
/etc/sudoers.d/hermes-services - nunca comandos livres ou argumentos
variaveis, para manter o principio de menor privilegio.

OpenVAS/Greenbone e diferente do Suricata/Zeek: nao e um servico
systemd, e uma stack Docker Compose (11 containers). "Ativo" aqui
significa docker-compose up -d ter corrido E a API GMP ja aceitar
pedidos - o container gvmd pode aparecer "healthy" no docker-compose
ps mas ainda estar a terminar migracoes internas, por isso a
confirmacao real e um pedido GMP de teste (get_version), em polling,
tal como ja e feito para esperar o fim de um scan em
openvas_reader.py._iniciar_e_esperar(). Uma vez arrancada, a stack
fica a correr (mesma logica do Suricata: nao se desliga a seguir,
so nao se forca a estar sempre ativa a partida).
"""
import subprocess
import time

from hermes.core.credentials import credentials

GREENBONE_DIR = "/mnt/hermes-data/backup-ubuntu/greenbone-community-edition"
OPENVAS_MAX_ESPERA_SEGUNDOS = 120
OPENVAS_INTERVALO_POLL_SEGUNDOS = 5
OPENVAS_UP_MAX_TENTATIVAS = 6
OPENVAS_UP_PAUSA_ENTRE_TENTATIVAS_SEGUNDOS = 20


def _correr(comando, cwd=None, timeout=30):
    """Corre um comando de sistema, devolve (sucesso, output)."""
    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=timeout, cwd=cwd
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
            logger.info("Suricata was already active.")
        return True
    if logger:
        logger.info("Suricata inactive - trying to start...")
    sucesso, saida = _correr(["sudo", "/usr/bin/systemctl", "start", "suricata"])
    if not sucesso:
        if logger:
            logger.error(f"Failed to start Suricata: {saida}")
        return False
    ativo, _ = _correr(["sudo", "/usr/bin/systemctl", "is-active", "suricata"])
    if ativo and logger:
        logger.info("Suricata started successfully.")
    elif not ativo and logger:
        logger.error("Suricata did not become active after start.")
    return ativo


def garantir_zeek(logger=None):
    """
    Confirma que o Zeek esta ativo (via zeekctl); arranca-o se nao
    estiver (zeekctl deploy). Devolve True se ficou/ja estava ativo.
    """
    sucesso, saida = _correr(["sudo", "/opt/zeek/bin/zeekctl", "status"])
    if sucesso and "running" in saida:
        if logger:
            logger.info("Zeek was already active.")
        return True
    if logger:
        logger.info("Zeek inactive - trying to start (zeekctl deploy)...")
    sucesso, saida = _correr(["sudo", "/opt/zeek/bin/zeekctl", "deploy"])
    if not sucesso:
        if logger:
            logger.error(f"Failed to start Zeek: {saida}")
        return False
    sucesso, saida = _correr(["sudo", "/opt/zeek/bin/zeekctl", "status"])
    ativo = sucesso and "running" in saida
    if ativo and logger:
        logger.info("Zeek started successfully.")
    elif not ativo and logger:
        logger.error("Zeek did not become active after deploy.")
    return ativo


def _openvas_gmp_responde():
    """
    Tenta um pedido GMP leve (get_version) contra a stack Greenbone.
    O gvm-cli, mesmo para get_version, fica preso a espera de input
    interativo (prompt "Enter username:") se nao receber credenciais
    - por isso sao sempre passadas aqui, tal como no openvas_reader.py,
    apesar de get_version em si nao exigir autenticacao a nivel do
    protocolo GMP. Sem isto o subprocesso ficava bloqueado ate ao
    timeout em cada tentativa, tornando o arranque muito mais lento
    do que devia. Devolve True/False.
    """
    conta = credentials.get("gvm_hermes")
    sucesso, saida = _correr(
        ["docker-compose", "run", "--rm", "gvm-tools",
         "gvm-cli", "--gmp-username", conta["username"], "--gmp-password", conta["password"],
         "socket", "--xml", "<get_version/>"],
        cwd=GREENBONE_DIR,
        timeout=20,
    )
    return sucesso and "<version>" in saida


def garantir_openvas(logger=None):
    """
    Confirma que a stack Docker do Greenbone/OpenVAS esta ativa e a
    API GMP ja responde; arranca-a (docker-compose up -d) se nao
    estiver. Ao contrario do Suricata/Zeek, "ativo" e confirmado por
    um pedido GMP real, nao so pelo estado dos containers - ver nota
    no topo do ficheiro. Devolve True se ficou (ou ja estava) pronta.

    O 'docker-compose up -d' pode falhar num arranque a frio se o
    container scap-data ainda nao tiver terminado de copiar os dados
    (fica "unhealthy" por uns segundos, e outros containers dependem
    dele estar saudavel). Isto e transitorio, nao um erro real - por
    isso o up -d e repetido ate OPENVAS_UP_MAX_TENTATIVAS vezes,
    porque repetir o comando e seguro (idempotente) e normalmente
    resolve-se sozinho.
    """
    if _openvas_gmp_responde():
        if logger:
            logger.info("OpenVAS/Greenbone was already active and responding.")
        return True

    sucesso = False
    saida = ""
    for tentativa in range(1, OPENVAS_UP_MAX_TENTATIVAS + 1):
        if logger:
            logger.info(
                f"OpenVAS/Greenbone inactive - running docker-compose up -d "
                f"(attempt {tentativa}/{OPENVAS_UP_MAX_TENTATIVAS})..."
            )
        sucesso, saida = _correr(
            ["docker-compose", "up", "-d"], cwd=GREENBONE_DIR, timeout=240
        )
        if sucesso:
            break
        if logger:
            logger.info(
                f"docker-compose up -d failed on attempt {tentativa} "
                f"(probably scap-data is still preparing data) - retrying "
                f"in {OPENVAS_UP_PAUSA_ENTRE_TENTATIVAS_SEGUNDOS}s..."
            )
        time.sleep(OPENVAS_UP_PAUSA_ENTRE_TENTATIVAS_SEGUNDOS)

    if not sucesso:
        if logger:
            logger.error(f"Failed to start the Greenbone stack after {OPENVAS_UP_MAX_TENTATIVAS} attempts: {saida}")
        return False

    esperado = 0
    while esperado < OPENVAS_MAX_ESPERA_SEGUNDOS:
        if _openvas_gmp_responde():
            if logger:
                logger.info("OpenVAS/Greenbone started successfully, GMP responding.")
            return True
        time.sleep(OPENVAS_INTERVALO_POLL_SEGUNDOS)
        esperado += OPENVAS_INTERVALO_POLL_SEGUNDOS

    if logger:
        logger.error(
            f"OpenVAS/Greenbone was not ready within the time limit "
            f"({OPENVAS_MAX_ESPERA_SEGUNDOS}s) after up -d."
        )
    return False


def garantir_dependencias(logger=None):
    """
    Chama todas as funcoes garantir_* conhecidas. Cada falha e
    isolada - uma dependencia falhar nao impede as outras de serem
    tentadas nem o PURPLE de arrancar.
    """
    resultados = {}
    for nome, funcao in [
        ("suricata", garantir_suricata),
        ("zeek", garantir_zeek),
        ("openvas", garantir_openvas),
    ]:
        try:
            resultados[nome] = funcao(logger)
        except Exception as e:
            if logger:
                logger.error(f"Unexpected error while ensuring '{nome}': {e}")
            resultados[nome] = False
    return resultados
