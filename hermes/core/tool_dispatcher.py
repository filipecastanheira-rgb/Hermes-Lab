"""
tool_dispatcher.py

Portao entre a decisao da IA (tool_calls vindos de
HermesIntelligence.gerar_com_tools) e a execucao real das ferramentas.

Regras de seguranca (fixas, nao negociaveis nesta fase):
- A IA nunca gera comandos livres. So pode escolher um nome de uma
  lista fixa pre-aprovada (FERRAMENTAS_PERMITIDAS_IA).
- Ferramentas com tipo_alvo="ip" (ex: nmap, openvas): o alvo passa
  sempre por lab_boundary.alvo_permitido() antes de qualquer
  execucao - a mesma validacao usada pelo endpoint manual /run_tool
  em purple_api.py.
- Ferramentas com tipo_alvo="interface_fixa" (ex: tshark): o TShark
  captura por interface de rede, nao por IP - nao faz sentido validar
  isso como endereco. Em vez disso, a interface e sempre fixa
  (interface_fixa), nunca escolhida pela IA - qualquer valor que a IA
  tente colocar no tool_call e substituido pela interface fixa antes
  do dispatch, tal como mission_target faz para o nmap em
  IntelligenceService.decide_action(). A protecao lab_boundary do
  TShark ja existe dentro de tshark_reader.py, aplicada pacote a
  pacote (Fase 0).
- Fase 1: apenas ferramentas on-demand simples e sincronas (nmap,
  tshark, openvas). Suricata/Zeek ficam de fora (sao so vigilancia
  continua via vigiar_todas()).
- AVISO (openvas): ao contrario do nmap/tshark, um scan OpenVAS pode
  demorar varios minutos - dispatch() para "run_openvas" bloqueia ate
  o scan terminar (ver aviso de arquitetura em
  hermes/tools/openvas/openvas_reader.py). Se isto se tornar um
  problema pratico no loop periodico de decide_action() (5 min, hoje arquivado em
  hermes/_archive/autonomia_experimental/),
  reavaliar (ex: rodar em thread separada ou aumentar o intervalo do
  loop quando openvas e chamado).
"""

from hermes.core.lab_boundary import MAX_ENDERECOS_ALVO, alvo_dentro_do_limite, alvo_permitido
from hermes.tools.agregador_ferramentas import ler_uma_vez_todas


FERRAMENTAS_PERMITIDAS_IA = {
    "run_nmap": {
        "nome_interno": "nmap",
        "descricao": "Runs an Nmap scan against a specific target inside the lab_boundary.",
        "tipo_alvo": "ip",
    },
    "run_tshark": {
        "nome_interno": "tshark",
        "descricao": "Captures traffic with TShark. The interface is always fixed (never chosen by the AI).",
        "tipo_alvo": "interface_fixa",
        "interface_fixa": "lo",
    },
    "run_openvas": {
        "nome_interno": "openvas",
        "descricao": "Runs an OpenVAS/Greenbone vulnerability scan against a specific target inside the lab_boundary. Heavy and slow scan (can take several minutes) - use sparingly.",
        "tipo_alvo": "ip",
    },
}


def construir_schemas_tools():
    schemas = []
    for nome_funcao, info in FERRAMENTAS_PERMITIDAS_IA.items():
        if info["tipo_alvo"] == "ip":
            descricao_target = "IP ou rede a analisar, tem de estar dentro do lab_boundary"
        else:
            descricao_target = "Not used - the capture interface is always fixed, ignored if sent"
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
                            "description": descricao_target,
                        }
                    },
                    "required": ["target"],
                },
            },
        })
    return schemas


def dispatch(tool_call):
    function = tool_call.get("function", {})
    nome_funcao = function.get("name", "")
    argumentos = function.get("arguments", {})

    if nome_funcao not in FERRAMENTAS_PERMITIDAS_IA:
        return {
            "ok": False,
            "erro": "Ferramenta '" + nome_funcao + "' nao esta na lista pre-aprovada para a IA.",
        }

    info = FERRAMENTAS_PERMITIDAS_IA[nome_funcao]
    nome_interno = info["nome_interno"]

    if info["tipo_alvo"] == "ip":
        target = str(argumentos.get("target", "")).strip()
        if not target:
            return {"ok": False, "erro": "Alvo em falta no tool_call."}
        if not alvo_permitido(target):
            return {
                "ok": False,
                "erro": "Alvo '" + target + "' fora do lab_boundary. Pedido recusado e nao executado.",
            }
        if not alvo_dentro_do_limite(target):
            return {
                "ok": False,
                "erro": "Target '" + target + "' is too large (limit: "
                        + str(MAX_ENDERECOS_ALVO) + " addresses). Request refused and not executed.",
            }
    else:
        target = info["interface_fixa"]

    eventos = ler_uma_vez_todas({nome_interno: target})

    return {
        "ok": True,
        "ferramenta": nome_interno,
        "target": target,
        "eventos": eventos,
    }
