"""
hermes_intelligence.py
Provider de IA do núcleo Hermes, unificado para viver dentro de
~/Hermes-Lab/orchestrator/ (não depende de /opt/hermes).

Config: config/intelligence_config.json
  {"provider": "none" | "openai" | "ollama", "model": "..."}
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "intelligence_config.json")


def _ler_config():
    if not os.path.exists(CONFIG_PATH):
        return {"provider": "none", "model": ""}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _guardar_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


class HermesIntelligence:
    def __init__(self):
        self.config = _ler_config()
        self.provider = self.config.get("provider", "none")
        self.model = self.config.get("model", "")
        print(f"[IA] Provider selecionado: {self.provider} (modelo: {self.model or 'n/a'})")

    def gerar(self, prompt):
        if self.provider == "none":
            return "[Hermes] Provider de IA não configurado (modo 'none')."

        if self.provider == "ollama":
            return self._usar_ollama(prompt)

        if self.provider == "openai":
            return self._usar_openai(prompt)

        return f"[Hermes] Provider '{self.provider}' desconhecido."

    def _usar_ollama(self, prompt):
        import requests
        model = self.model or "llama3.2:3b"
        try:
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=30,
            )
            if r.status_code != 200:
                return f"[Hermes] Erro Ollama: {r.text[:200]}"
            return r.json().get("response", "")
        except Exception as e:
            return f"[Hermes] Ollama não está a correr ou não está acessível: {e}"

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
                "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "tools": tools,
                    "stream": False,
                },
                timeout=30,
            )
            if r.status_code != 200:
                return {"erro": f"[Hermes] Erro Ollama (tools): {r.text[:200]}"}
            data = r.json()
            message = data.get("message", {})
            return {
                "tool_calls": message.get("tool_calls", []),
                "content": message.get("content", ""),
            }
        except Exception as e:
            return {"erro": f"[Hermes] Ollama (tools) nao esta a correr ou nao esta acessivel: {e}"}

    def _usar_openai(self, prompt):
        import requests
        api_key = self.config.get("api_key", "")
        model = self.model or "gpt-4o-mini"
        if not api_key:
            return "[Hermes] OpenAI API key não configurada."
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                timeout=15,
            )
            if r.status_code != 200:
                return f"[Hermes] Erro OpenAI ({r.status_code}): {r.text[:200]}"
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[Hermes] Erro ao contactar OpenAI: {e}"


def definir_provider(provider, model=""):
    config = {"provider": provider, "model": model}
    if provider == "openai":
        antigo = _ler_config()
        if antigo.get("api_key"):
            config["api_key"] = antigo["api_key"]
    _guardar_config(config)
    return config
