"""
hermes_intelligence.py
Provider de IA do núcleo Hermes, unificado para viver dentro de
~/Hermes-Lab/ (não depende de /opt/hermes).

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
            return "[Hermes] AI provider not configured (mode 'none')."

        if self.provider == "ollama":
            return self._usar_ollama(prompt)

        if self.provider == "openai":
            return self._usar_openai(prompt)

        return f"[Hermes] Unknown provider '{self.provider}'."

    def _usar_ollama(self, prompt):
        import requests
        model = self.model or "llama3.2:3b"
        try:
            # Timeout aumentado de 30 -> 120 -> 200s (2026-08-30). 120s ainda
            # falhou numa primeira execucao a seguir a um restart do Hermes
            # (Ollama "frio" + prompt pesado do relatorio de execucao,
            # combinados). Uma segunda tentativa a seguir, com o modelo ja
            # "quente", levou ~40s sem problema. 200s da margem para o pior
            # caso (frio + prompt grande) sem arriscar timeouts falsos.
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=200,
            )
            if r.status_code != 200:
                return f"[Hermes] Ollama error: {r.text[:200]}"
            return r.json().get("response", "")
        except Exception as e:
            return f"[Hermes] Ollama is not running or not reachable: {e}"

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
