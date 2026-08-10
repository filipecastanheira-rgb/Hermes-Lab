# Hermes-Lab

Plataforma pessoal de cibersegurança — orquestra deteção (BLUE), serviço
contínuo com API (PURPLE), IA local (Ollama), e um conjunto extensível
de ferramentas de rede (Suricata, Nmap, TShark), tudo através de um
único CLI.

Projeto de aprendizagem, construído em paralelo com um curso de
cibersegurança, com o objetivo de servir como prática para o EC-Council
CEH e como peça de portefólio para GRC/Cloud Security.

## Arquitetura

```
HERMES (hermes_cli.py → orchestrator.py → CommandRouter)
   │
   ├── BLUE   — deteção: scanner, alert_engine, correlator, auth_monitor, log_manager
   ├── PURPLE — serviço contínuo: API HTTP, auth por token, rate limit, dashboard
   ├── IA     — Ollama (local, grátis) via hermes/core/hermes_intelligence.py
   └── TOOLS  — capacidades partilhadas, não pertencem a nenhum team:
        ├── Suricata (IDS/IPS)
        ├── Nmap (scanning)
        └── TShark (captura de pacotes)
```

Princípio central: **as ferramentas são capacidades do Hermes, não
propriedade de um team**. BLUE/RED/PURPLE consomem-nas através do
`agregador_ferramentas.py`, que expõe cada ferramenta pelo mesmo
contrato — `parse_evento`, `ler_uma_vez`, `vigiar` — independentemente
de como funciona por dentro.

Toda a ferramenta que aponta a um alvo de rede passa primeiro por
`hermes/core/lab_boundary.py`, que só permite tráfego dentro de redes
explicitamente autorizadas (por defeito, só `127.0.0.0/8`).

## A correr

```bash
git clone https://github.com/filipecastanheira-rgb/Hermes-Lab.git
cd Hermes-Lab/orchestrator

# BLUE — scan e deteção
python3 hermes_cli.py blue blue_scan 127.0.0.1 22

# PURPLE — API + dashboard visual
python3 hermes_cli.py purple purple_start
# depois, no browser: http://localhost:5000/dashboard/view?token=<ver config/purple_auth.json>

# IA local
python3 hermes_cli.py ia ia_set ollama phi3:mini
python3 hermes_cli.py ia ia_status
```

As dependências Python (`flask`, `requests`) instalam-se sozinhas no
primeiro arranque — não é preciso `pip install` manual.

## Estado atual

- ✅ BLUE — pipeline de deteção completo e testado
- ✅ PURPLE — API, autenticação, dashboard visual
- ✅ IA local — Ollama/phi3:mini integrado
- ✅ Ferramentas — Suricata, Nmap, TShark, todas no mesmo contrato
- ✅ Fronteira de segurança (`lab_boundary`) — nunca corre contra rede fora do laboratório
- 🔜 RED — planeado, vai reutilizar as mesmas ferramentas do BLUE
- 🔜 Mais ferramentas (Zeek, etc.)

## Segurança e âmbito

Este projeto corre exclusivamente contra um laboratório controlado e
isolado (`127.0.0.0/8` e, mais tarde, uma rede de VMs dedicada). Nunca
foi usado, nem se destina a ser usado, contra redes ou sistemas de
terceiros sem autorização.
