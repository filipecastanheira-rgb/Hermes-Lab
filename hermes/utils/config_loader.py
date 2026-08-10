"""
config_loader.py
Leitura e escrita centralizada do hermes.yaml.

Antes, cada módulo (bootstrap, entrypoint, orchestrator, intelligence,
runtime) tinha a sua própria cópia de ler_yaml()/escrever_yaml(). Isso
significava 5 pontos de falha diferentes para o mesmo ficheiro. Agora
há um só.
"""

import os

BASE_DIR = "/opt/hermes"
CONFIG_PATH = os.path.join(BASE_DIR, "config", "hermes.yaml")
LOG_DIR = os.path.join(BASE_DIR, "logs")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")


def ler_yaml(caminho=CONFIG_PATH):
    """
    Lê um YAML simples (chave: valor, uma por linha) e devolve um dict.
    Não usa biblioteca externa de propósito, para não acrescentar
    dependências ao bootstrap.
    """
    config = {}
    if not os.path.exists(caminho):
        return config

    with open(caminho, "r") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            if ":" not in linha:
                continue
            chave, valor = linha.split(":", 1)
            valor = valor.strip().strip('"')
            config[chave.strip()] = valor
    return config


def escrever_yaml(config, caminho=CONFIG_PATH):
    """
    Escreve um dict simples para YAML (chave: valor).
    Booleanos ficam como 'true'/'false' em minúsculas, como o resto
    do projeto já espera.
    """
    linhas = []
    for chave, valor in config.items():
        if isinstance(valor, bool):
            valor_str = "true" if valor else "false"
        else:
            valor_str = str(valor)
        linhas.append(f"{chave}: {valor_str}\n")

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w") as f:
        f.writelines(linhas)


def atualizar_chave(chave, valor, caminho=CONFIG_PATH):
    """
    Lê, atualiza uma chave, e volta a escrever. Usado pelo hermesctl
    e por comandos internos (ex: mudar de modo em runtime).
    """
    config = ler_yaml(caminho)
    config[chave] = valor
    escrever_yaml(config, caminho)
    return config
