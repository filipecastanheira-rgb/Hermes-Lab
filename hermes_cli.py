#!/usr/bin/env python3

import sys
import subprocess
import importlib


def garantir_dependencias():
    """
    Verifica se as dependências essenciais (flask, requests) estão
    instaladas, e instala-as automaticamente se não estiverem — sem
    precisar de venv ativa nem de comandos manuais. Corre sempre que
    o Hermes arranca, silenciosamente se já estiver tudo OK.
    """
    obrigatorias = ["flask", "requests"]
    em_falta = []

    for pacote in obrigatorias:
        try:
            importlib.import_module(pacote)
        except ImportError:
            em_falta.append(pacote)

    if not em_falta:
        return

    print(f"[hermes_cli] A instalar dependências em falta: {em_falta}...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--break-system-packages", "--quiet", *em_falta
        ])
        print("[hermes_cli] Dependências instaladas com sucesso.")
    except subprocess.CalledProcessError as e:
        print(f"[hermes_cli] ERRO ao instalar dependências automaticamente: {e}")
        print("[hermes_cli] Tenta manualmente: pip install --break-system-packages flask requests")
        sys.exit(1)


garantir_dependencias()

from orchestrator import HermesOrchestrator



def main():
    if len(sys.argv) < 2:
        print("[CLI] Erro: tens de indicar o modo (blue, red, purple).")
        sys.exit(1)

    mode = sys.argv[1].lower()

    # comando opcional (ex: blue_scan); por defeito corre o "<modo>_test"
    comando = sys.argv[2] if len(sys.argv) > 2 else f"{mode}_test"
    args_extra = sys.argv[3:]

    print(f"[CLI] Modo selecionado: {mode}")
    print(f"[CLI] Comando: {comando} {args_extra}")

    orch = HermesOrchestrator(mode)
    orch.run(comando, *args_extra)


if __name__ == "__main__":
    main()
