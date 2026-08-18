"""
tool_dispatcher.py

Portao entre a decisao da IA (tool_calls vindos de
HermesIntelligence.gerar_com_tools) e a execucao real das ferramentas.

Regras de seguranca (fixas, nao negociaveis nesta fase):
- A IA nunca gera comandos livres. So pode escolher um nome de uma
  lista fixa pre-aprovada (FERRAMENTAS_PERMITIDAS_IA).
- Todo o alvo passa sempre por lab_boundary.alvo_permitido() antes de
  qualquer execucao - exatamente a mesma validacao usada pelo
  endpoint manual /run_tool em purple_api.py.
- Fase 1: apenas ferramentas on-demand simples e sincronas (nmap,
  tshark). Suricata/Zeek ficam de fora (sao so vigilancia continua
  via vigiar_todas()). OpenVAS fica de fora ate a integracao GMP
  estar fechada do lado do ChatGPT - a estrutura aqui ja e pensada
  para ser extensivel quando isso acontecer.
"""

from hermes.core.lab_boundary import alvo_permitido
from hermes.tools.agregador_ferramentas import ler_uma_vez_todas


# Lista fixa de ferramentas que a IA pode pedir. Acrescentar uma
# ferramenta nova aqui e o unico sitio a mexer para a expor a IA -
# nunca inventar chamadas fora desta lista.
FERRAMENTAS_PERMITIDAS_IA = {
    "run_nmap": {
        "nome_interno": "nmap",
        "descricao": "Corre um scan Nmap a um alvo especifico dentro do lab_boundary.",
    },
    "run_tshark": {
        "nome_interno": "tshark",
        "descricao": "Captura trafego com TShark num alvo/interface dentro do lab_boundary.",
    },
}


def construir_schemas_tools():
    """
    Gera a lista de schemas JSON (formato Ollama /api/chat) a partir
    de FERRAMENTAS_PERMITIDAS_IA, para passar a gerar_com_tools().
    """
    schemas = []
    for nome_funcao, info in FERRAMENTAS_PERMITIDAS_IA.items():
        schemas.append({
            "type": "function",
            "function": {
                "name": nome_funcao,
                "description": info["descricao"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "IP ou rede a analisar, tem de estar dentro do lab_boundary",
                        }
                    },
                    "required": ["target"],
                },
            },
        })
    return schemas


def dispatch(tool_call: dict) -> dict:
    """
    Recebe UM tool_call (um item da lista tool_calls devolvida por
    gerar_com_tools) e, se tudo validar, executa a ferramenta real.

    Nunca corre nada fora da lista pre-aprovada nem fora do
    lab_boundary. Devolve sempre um dict com "ok" (bool) e detalhe.
    """
    function = tool_call.get("function", {})
    nome_funcao = function.get("name", "")
    argumentos = function.get("arguments", {})
    target = str(argumentos.get("target", "")).strip()

    if nome_funcao not in FERRAMENTAS_PERMITIDAS_IA:
        return {
            "ok": False,
            "erro": f"Ferramenta '{nome_funcao}' nao esta na lista pre-aprovada para a IA.",
        }

    if not target:
        return {"ok": False, "erro": "Alvo em falta no tool_call."}

    if not alvo_permitido(target):
        return {
            "ok": False,
            "erro": f"Alvo '{target}' fora do lab_boundary. Pedido recusado e nao executado.",
        }

    nome_interno = FERRAMENTAS_PERMITIDAS_IA[nome_funcao]["nome_interno"]
    eventos = ler_uma_vez_todas({nome_interno: target})

    return {
        "ok": True,
        "ferramenta": nome_interno,
        "target": target,
        "eventos": eventos,
    }
