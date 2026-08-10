# Hermes-Lab/orchestrator — pacote definitivo (substitui tudo)

A tua pasta `~/Hermes-Lab/orchestrator/` ficou com a estrutura
desalinhada — `purple/` e `utils/` soltos na raiz, sem `hermes/`
por cima, e sem `blue/`/`modes/`/`config/` de todo. Provavelmente
de zips anteriores extraídos em momentos diferentes.

Em vez de continuarmos a corrigir aos bocados, aqui está **tudo junto,
testado do zero neste momento**, para substituíres de uma vez.

## Como instalar (limpa tudo e substitui)

```bash
cd ~/Hermes-Lab

# 1) guarda uma cópia de segurança da pasta atual, por precaução
mv orchestrator orchestrator_old_backup

# 2) extrai este zip diretamente para o sítio certo
unzip hermes_orchestrator_definitivo.zip -d orchestrator

cd orchestrator
```

## Testar (mesmos testes de sempre)

```bash
python3 hermes_cli.py blue blue_scan 127.0.0.1 22
python3 hermes_cli.py purple purple_status
python3 hermes_cli.py purple purple_start   # Ctrl+C para parar
```

## Depois de confirmares que está tudo a funcionar

```bash
rm -rf ~/Hermes-Lab/orchestrator_old_backup
```

## Para o Docker (`/opt/hermes-python`)

Depois de confirmares que este pacote funciona no host, repete a
cópia para o Docker, mas desta vez apagando primeiro o que lá está,
para não misturar com os restos antigos:

```bash
sudo rm -rf /opt/hermes-python/*
sudo cp -r ~/Hermes-Lab/orchestrator/* /opt/hermes-python/

cd /opt/hermes-python
docker build -t hermes-python:latest .
docker stop hermes-python 2>/dev/null
docker rm hermes-python 2>/dev/null
docker run -d --name hermes-python -p 9080:5000 -v /opt/hermes-python:/app hermes-python:latest
docker logs -f hermes-python
```

## O que está neste pacote (tudo testado agora mesmo, do zero)

```
hermes_cli.py, orchestrator.py, purple_client.py
commands/  (router, blue, purple, red, __init__)
config/hermes_config.json
hermes/blue/     — scanner, alert_engine, alert_rules, auth_monitor,
                   correlator, log_manager, health_check, watchdog
hermes/modes/    — mode_loader, mode_profile, mode_router
hermes/purple/   — todos os módulos PURPLE, incluindo purple_health.py
                   e purple_watchdog.py próprios (não os do BLUE)
hermes/utils/    — config_loader, metrics
```
