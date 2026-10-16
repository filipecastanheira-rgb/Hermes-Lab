# ia.py
# Comandos para gerir e testar o provider de IA do Hermes.

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hermes.core.hermes_intelligence import HermesIntelligence, definir_provider


def ia_status():
    ia = HermesIntelligence()
    resposta = ia.gerar("Hermes, confirma que estás operacional numa frase curta.")
    print(f"[IA] Resposta: {resposta}")


def ia_set(provider="none", model="", *args, **kwargs):
    """
    Uso: python3 hermes_cli.py ia ia_set ollama phi3:mini
    """
    config = definir_provider(provider, model)
    print(f"[IA] Provider atualizado: {config}")


def register(router):
    router.register("ia_status", ia_status)
    router.register("ia_set", ia_set)
