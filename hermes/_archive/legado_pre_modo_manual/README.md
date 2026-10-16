# Legacy code from before manual mode (archived 2026-10-16)

This is the previous structure of Hermes-Lab, kept for history. Nothing here is imported or run.

- `mode_loader.py`, `mode_profile.py`: the RED/BLUE/PURPLE run-mode system. The active code keeps only the module loader, now `hermes/blue/pipeline.py`, without the concept of a mode.
- `orchestrator.py`, `commands/`: the command-line router (`blue_scan`, `ia_set`, ...). Replaced by `hermes_cli.py`, which starts the service directly. The AI provider is now configured by copying `config/intelligence_config.example.json`.
- `purple_client.py`: a development stub that only printed what it would have sent.
- `blue/`: duplicated or superseded BLUE modules (a second TShark reader, a watchdog and a health check replaced by the PURPLE ones, and the advanced alert rules that only the old CLI loaded).
- `utils/config_loader.py`: a shared config loader that nothing used.
