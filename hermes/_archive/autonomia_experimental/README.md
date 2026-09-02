# Autonomia experimental — arquivado (2026-08-30)

## O que é isto

Este código foi a implementação real do loop autónomo de decisão do
Hermes (Fase 1 de autonomia): a cada 5 minutos, a IA local (Ollama,
llama3.2:3b) analisava o contexto recente e decidia sozinha se e qual
tool pré-aprovada correr (nmap/tshark/openvas), dentro do
`lab_boundary`, com o alvo sempre fixo (nunca escolhido pela IA).
Também gerava relatórios automáticos em linguagem natural.

## Porque foi arquivado, não apagado

Testes empíricos diretos ao Ollama (2026-08-29, documentados na
memória do projeto e no README) mostraram que o modelo local decide
bem numa única chamada quando a pergunta tem direção clara (5/5 numa
pergunta orientada a vulnerabilidades), mas **não encadeia decisões**
— não reage a um resultado suspeito chamando outra tool sozinho,
mesmo quando isso lhe é pedido explicitamente. Isto tornava a
"autonomia" real limitada a uma decisão pontual por ciclo, sem o
comportamento de investigação que era o objetivo original.

Decisão tomada: o Hermes passou a operar em modo manual (o utilizador
escolhe a tool e o alvo; ver `hermes/purple/purple_runner.py` e
`hermes/purple/purple_api.py` para o estado atual). Este código fica
aqui, funcional e coerente, para o caso de um dia — com um modelo
mais capaz (ex: a Fase 2 de cloud alguma vez avançar) — fazer sentido
retomar a autonomia. Não é lixo nem um rascunho; era código testado
e a funcionar dentro dos limites que se provaram existir.

## Conteúdo

- `decide_action_loop.py` — as constantes (`PERGUNTAS_ROTATIVAS_IA`,
  `SEVERIDADES_RELEVANTES`), o helper `_timestamp_para_epoch`, e a
  função `executar_ciclo_decisao_autonoma()` que encapsula o que
  antes corria dentro do `_loop_principal()` do `purple_runner.py` a
  cada `_intervalo_decisao_ia` segundos.

## Como retomar, se um dia fizer sentido

1. Confirmar primeiro, com o mesmo rigor empírico usado em 2026-08-29,
   que o modelo/hardware disponível nessa altura já encadeia decisões
   de forma fiável (repetir os testes diretos ao endpoint de chat,
   não assumir que "é maior, logo resolve").
2. Se confirmado: importar `executar_ciclo_decisao_autonoma()` a
   partir de `_loop_principal()`, restaurar as variáveis de estado
   (`_ultima_decisao_ia`, `_intervalo_decisao_ia`,
   `_ultimo_relatorio_ia`, `_intervalo_relatorio_diario`,
   `_indice_pergunta_ia`) no `__init__` do `PurpleRunner`, e voltar a
   chamar a função no loop.
3. `IntelligenceService.decide_action()` e `escrever_relatorio()`
   continuam no código ativo (`hermes/core/intelligence_service.py`)
   — não foram arquivados, porque `escrever_relatorio()` também é
   usado no modo manual atual (relatório por execução).
