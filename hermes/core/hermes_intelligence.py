"""
hermes_intelligence.py
Provider de IA do núcleo Hermes, unificado para viver dentro de
~/Hermes-Lab/ (não depende de /opt/hermes).

Config: config/intelligence_config.json
  {"provider": "none" | "openai" | "ollama", "model": "...",
   "ollama_url": "http://localhost:11434"}
  "ollama_url" is optional; it defaults to http://localhost:11434.
"""

import json
import os
import threading
import time

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "intelligence_config.json")
DEFAULT_OLLAMA_URL = "http://localhost:11434"

AI_STATE_TTL = 30        # seconds the last known AI state is reused
CONNECT_TIMEOUT = 5      # seconds to establish a connection

_estado_ia = {"estado": "unknown", "ts": 0.0}
_estado_lock = threading.Lock()


def _ler_config():
    if not os.path.exists(CONFIG_PATH):
        return {"provider": "none", "model": ""}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _guardar_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def _registar_estado(estado):
    with _estado_lock:
        _estado_ia["estado"] = estado
        _estado_ia["ts"] = time.time()


def _verificar_estado():
    import requests
    config = _ler_config()
    if config.get("provider") != "ollama":
        return "none"
    url_cloud = (config.get("ollama_url") or DEFAULT_OLLAMA_URL).rstrip("/")
    candidatos = []
    if url_cloud != DEFAULT_OLLAMA_URL:
        candidatos.append(("cloud", url_cloud))
    candidatos.append(("local", DEFAULT_OLLAMA_URL))
    for estado, url in candidatos:
        try:
            r = requests.get(f"{url}/api/version", timeout=(CONNECT_TIMEOUT, 5))
            if r.status_code == 200:
                return estado
        except requests.exceptions.RequestException:
            pass
    return "none"


def obter_estado_ia():
    """Last known AI state: cloud, local, none or unknown.
    Re-checked at most once every AI_STATE_TTL seconds."""
    with _estado_lock:
        if _estado_ia["ts"] and (time.time() - _estado_ia["ts"]) <= AI_STATE_TTL:
            return _estado_ia["estado"]
    estado = _verificar_estado()
    _registar_estado(estado)
    return estado


class HermesIntelligence:
    def __init__(self):
        self.config = _ler_config()
        self.provider = self.config.get("provider", "none")
        self.model = self.config.get("model", "")
        self.ollama_url = (self.config.get("ollama_url") or DEFAULT_OLLAMA_URL).rstrip("/")
        self.url_local = DEFAULT_OLLAMA_URL
        self.tem_fallback = self.ollama_url != DEFAULT_OLLAMA_URL
        self.last_source = None
        print(f"[IA] Provider selecionado: {self.provider} (modelo: {self.model or 'n/a'})")

    def gerar(self, prompt):
        if self.provider == "none":
            return "[Hermes] AI provider not configured (mode 'none')."

        if self.provider == "ollama":
            return self._usar_ollama(prompt)

        if self.provider == "openai":
            return self._usar_openai(prompt)

        return f"[Hermes] Unknown provider '{self.provider}'."

    def _usar_ollama(self, prompt):
        import requests
        model = self.model or "llama3.2:3b"
        if self.tem_fallback:
            destinos = [("Cloud AI", self.ollama_url), ("Local AI", self.url_local)]
        else:
            destinos = [("Local AI", self.url_local)]
        self.last_source = None
        ultimo_erro = None
        for rotulo, url in destinos:
            try:
                # Read timeout raised 30 -> 120 -> 200 s (2026-08-30): a cold
                # Ollama plus a heavy execution-report prompt failed at 120 s.
                # The 200 s read timeout is unchanged for the cloud instance
                # (2 cores), not yet measured there. The connection timeout is
                # separate and short, so an unreachable cloud fails fast.
                r = requests.post(
                    f"{url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                    timeout=(CONNECT_TIMEOUT, 200),
                )
            except requests.exceptions.ConnectionError as e:
                # Connection failure only: fall back to the next destination.
                ultimo_erro = e
                continue
            except Exception as e:
                # Read timeout or anything else: the destination was reached,
                # so no fallback.
                self.last_source = rotulo
                return f"[Hermes] Ollama is not running or not reachable: {e}"
            self.last_source = rotulo
            if r.status_code != 200:
                return f"[Hermes] Ollama error: {r.text[:200]}"
            _registar_estado("cloud" if rotulo == "Cloud AI" else "local")
            return r.json().get("response", "")
        _registar_estado("none")
        return f"[Hermes] Ollama is not running or not reachable: {ultimo_erro}"

    def gerar_com_tools(self, prompt, tools):
        """
        Chama o Ollama via /api/chat com tool calling nativo (nao /api/generate).
        Devolve tool_calls estruturados (pode ser lista vazia) em vez de texto livre.
        Nao executa nada aqui - quem recebe o resultado decide se despacha.
        """
        import requests
        model = self.model or "llama3.2:3b"
        try:
            r = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "tools": tools,
                    "stream": False,
                },
                timeout=30,
            )
            if r.status_code != 200:
                return {"erro": f"[Hermes] Ollama (tools) error: {r.text[:200]}"}
            data = r.json()
            message = data.get("message", {})
            return {
                "tool_calls": message.get("tool_calls", []),
                "content": message.get("content", ""),
            }
        except Exception as e:
            return {"erro": f"[Hermes] Ollama (tools) is not running or not reachable: {e}"}

    def _usar_openai(self, prompt):
        import requests
        api_key = self.config.get("api_key", "")
        model = self.model or "gpt-4o-mini"
        if not api_key:
            return "[Hermes] OpenAI API key not configured."
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                timeout=15,
            )
            if r.status_code != 200:
                return f"[Hermes] OpenAI error ({r.status_code}): {r.text[:200]}"
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[Hermes] Error contacting OpenAI: {e}"


def definir_provider(provider, model=""):
    config = {"provider": provider, "model": model}
    if provider == "openai":
        antigo = _ler_config()
        if antigo.get("api_key"):
            config["api_key"] = antigo["api_key"]
    _guardar_config(config)
    return config
