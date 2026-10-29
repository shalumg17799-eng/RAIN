"""LLM provider adapter: none | ollama (OSS) | azure_openai (Azure) | anthropic (Claude API). Skills call complete(); provider is config only."""
import json
import os
import urllib.request

from dif.config import settings


class LLMUnavailable(Exception):
    pass


def _post(url, body, headers=None, timeout=60):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        raise LLMUnavailable(str(e)) from e


def complete(prompt: str) -> str:
    p = settings.llm_provider
    if p == "ollama":
        r = _post(os.getenv("DIF_OLLAMA_URL", "http://localhost:11434") + "/api/generate",
                  {"model": os.getenv("DIF_LLM_MODEL", "qwen2.5:0.5b"), "prompt": prompt, "stream": False,
                   "options": {"temperature": 0}}, timeout=180)
        return r["response"]
    if p == "azure_openai":
        ep, dep = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/"), os.environ["AZURE_OPENAI_DEPLOYMENT"]
        r = _post(f"{ep}/openai/deployments/{dep}/chat/completions?api-version=2024-06-01",
                  {"messages": [{"role": "user", "content": prompt}], "temperature": 0},
                  {"api-key": os.environ["AZURE_OPENAI_API_KEY"]})
        return r["choices"][0]["message"]["content"]
    if p == "anthropic":  # Claude Messages API over plain HTTPS (no SDK dependency); key from ANTHROPIC_API_KEY
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
        base = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
        r = _post(f"{base}/v1/messages",
                  {"model": os.getenv("DIF_ANTHROPIC_MODEL", "claude-sonnet-5-5"),
                   "max_tokens": int(os.getenv("DIF_LLM_MAX_TOKENS", "4096")),
                   "messages": [{"role": "user", "content": prompt}]},
                  {"x-api-key": key, "anthropic-version": os.getenv("ANTHROPIC_VERSION", "2023-06-01")}, timeout=120)
        return "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
    raise LLMUnavailable(f"DIF_LLM_PROVIDER={p}")


def complete_json(prompt: str, default=None):
    """complete() for prompts that ask for JSON: extracts the first JSON object/array from the reply. Returns
    `default` (or raises LLMUnavailable when default is None) if the reply holds no parseable JSON."""
    import re
    text = complete(prompt)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    candidate = m.group(1) if m else text
    start = min([i for i in (candidate.find("{"), candidate.find("[")) if i >= 0], default=-1)
    if start >= 0:
        for end in range(len(candidate), start, -1):
            try:
                return json.loads(candidate[start:end])
            except json.JSONDecodeError:
                continue
    if default is None:
        raise LLMUnavailable("model reply contained no JSON")
    return default


def available() -> bool:
    return settings.llm_provider != "none"
