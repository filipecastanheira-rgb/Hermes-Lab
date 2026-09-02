"""
decide_action_loop.py — ARQUIVADO (2026-08-30)

Ver README.md nesta mesma pasta para o contexto completo de porque
este código foi retirado do purple_runner.py ativo. Resumo: a IA
local decide bem numa unica chamada com uma pergunta orientada, mas
nao encadeia decisoes sozinha - a autonomia real ficava limitada a
uma decisao pontual por ciclo. O Hermes passou a modo manual.

Este ficheiro nao e importado por nada em producao. E preservado como
referencia funcional, nao como codigo morto sem contexto.

Uso original (dentro de PurpleRunner._loop_principal(), a cada
_intervalo_decisao_ia segundos):

    from hermes._archive.autonomia_experimental.decide_action_loop import (
        executar_ciclo_decisao_autonoma,
    )
    ...
    self._indice_pergunta_ia = executar_ciclo_decisao_autonoma(
        intelligence_service=self._intelligence_service,
        alerts=self.alerts,
        logger=self.logger,
        indice_pergunta_ia=self._indice_pergunta_ia,
        ultimo_relatorio_ia=self._ultimo_relatorio_ia,
        intervalo_relatorio_diario=self._intervalo_relatorio_diario,
    )
"""

from datetime import datetime, timezone


SEVERIDADES_RELEVANTES = {"medium", "high", "critical"}

# Perguntas rodadas no loop autonomo (2026-08-29). Antes havia so uma
# pergunta generica repetida para sempre, o que levava a IA a escolher
# quase sempre a mesma tool (confirmado empiricamente: com a pergunta
# generica, 4-5 em 5 tentativas escolhiam nmap; com uma pergunta
# orientada a vulnerabilidades, 5 em 5 escolheram openvas). A decisao
# de QUE TOOL correr continuava inteiramente da IA em cada chamada -
# isto so variava a pergunta que lhe era feita, para lhe dar hipotese
# real de considerar cada area, em vez de a forcar a uma ferramenta
# certa. Mesmo assim, nao resolveu o problema de fundo: a IA nunca
# encadeava uma segunda decisao a partir do resultado da primeira.
PERGUNTAS_ROTATIVAS_IA = [
    "Ha algum evento recente que precise de investigacao?",
    "Ha portas ou servicos inesperados a correr no alvo?",
    "Ha trafego de rede anomalo ou suspeito nos eventos recentes?",
    "Ha vulnerabilidades conhecidas por corrigir no alvo?",
]


def _timestamp_para_epoch(valor):
    """
    Converte um timestamp ISO (como gravado em clean/) para epoch
    segundos, para comparar "aconteceu depois do ultimo relatorio".
    Devolve 0 se nao for possivel interpretar (nunca rebenta o loop).
    """
    if not isinstance(valor, str) or not valor.strip():
        return 0
    try:
        dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _tem_eventos_relevantes_desde_ultimo_relatorio(intelligence_service, logger, ultimo_relatorio_ia):
    """
    True se houver algum evento com severidade medium/high/critical
    gravado em clean/ depois do ultimo relatorio da IA.
    """
    from hermes.core.context_builder import load_events

    try:
        eventos = load_events(intelligence_service.context_config)
    except Exception as e:
        logger.error(f"Falha ao carregar eventos para verificar relatorio: {e}")
        return False

    for evento in eventos:
        severidade = str(evento.get("severity", "info")).lower()
        if severidade not in SEVERIDADES_RELEVANTES:
            continue
        if _timestamp_para_epoch(evento.get("timestamp")) > ultimo_relatorio_ia:
            return True
    return False


def executar_ciclo_decisao_autonoma(
    *,
    intelligence_service,
    alerts,
    logger,
    indice_pergunta_ia,
    ultimo_relatorio_ia,
    intervalo_relatorio_diario,
):
    """
    Um ciclo do que antes corria dentro do _loop_principal() do
    PurpleRunner. Escolhe a proxima pergunta rotativa, chama
    decide_action(), regista alertas para cada acao tomada/recusada,
    e gera um relatorio da IA se houver evento relevante ou se ja
    passou o intervalo diario sem nenhum.

    Devolve o indice_pergunta_ia atualizado (o chamador deve guardar
    isto e o timestamp do ultimo relatorio, tal como fazia antes).
    """
    pergunta = PERGUNTAS_ROTATIVAS_IA[indice_pergunta_ia % len(PERGUNTAS_ROTATIVAS_IA)]

    try:
        resultado = intelligence_service.decide_action(pergunta)
        for acao in resultado.get("acoes", []):
            r = acao["resultado"]
            if r.get("ok"):
                alerts.emitir_alerta(
                    severidade="INFO",
                    origem="hermes_ia",
                    descricao=f"IA correu '{r.get('ferramenta')}' em '{r.get('target')}'",
                    contexto={"eventos_capturados": len(r.get("eventos", []))},
                )
            else:
                alerts.emitir_alerta(
                    severidade="INFO",
                    origem="hermes_ia",
                    descricao=f"IA tentou uma acao mas foi recusada: {r.get('erro')}",
                    contexto={},
                )
    except Exception as e:
        logger.error(f"Decisao autonoma da IA falhou: {e}")

    try:
        tem_relevante = _tem_eventos_relevantes_desde_ultimo_relatorio(
            intelligence_service, logger, ultimo_relatorio_ia
        )
        import time
        tempo_desde_ultimo = time.time() - ultimo_relatorio_ia
        if tem_relevante or tempo_desde_ultimo >= intervalo_relatorio_diario:
            motivo = "evento_relevante" if tem_relevante else "resumo_diario"
            intelligence_service.escrever_relatorio(motivo)
    except Exception as e:
        logger.error(f"Falha ao gerar relatorio da IA: {e}")

    return indice_pergunta_ia + 1
