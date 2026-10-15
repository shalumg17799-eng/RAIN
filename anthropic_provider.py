"""Anthropic Claude Messages API Adapter.

Supports native Anthropic API keys (e.g. claude-3-5-sonnet-20241022, claude-3-haiku-20240307).
Directly communicates with https://api.anthropic.com/v1/messages using standard-library urllib.
"""

from __future__ import annotations

import json
from typing import Any
from pydantic import SecretStr

from insights.contracts.gateway import Usage
from insights.gateway.base import ProviderError, ProviderRequest, ProviderResponse, estimate_usage
from insights.gateway.openai_compat import Transport, UrllibTransport, _schema_directive

DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        model: str = "claude-3-5-sonnet-20241022",
        url: str = DEFAULT_ANTHROPIC_URL,
        timeout_s: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        self._key = api_key
        self._model = model
        self._url = url
        self._timeout = timeout_s
        self._transport = transport or UrllibTransport()

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        system_prompts: list[str] = []
        user_messages: list[dict[str, str]] = []

        for m in request.messages:
            if m.role == "system":
                system_prompts.append(m.content)
            else:
                user_messages.append({"role": m.role, "content": m.content})

        if request.response_schema is not None:
            directive = _schema_directive(request.response_schema)
            system_prompts.append(directive)

        if not user_messages:
            user_messages.append({"role": "user", "content": "Begin."})

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "messages": user_messages,
        }
        if system_prompts:
            payload["system"] = "\n\n".join(system_prompts)
        if request.temperature > 0.0:
            payload["temperature"] = request.temperature

        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._key.get_secret_value(),
            "anthropic-version": ANTHROPIC_VERSION,
        }

        resp = self._transport.post(self._url, headers, body, self._timeout)
        if resp.status != 200:
            raise ProviderError(f"Anthropic returned HTTP status {resp.status}")

        try:
            data = json.loads(resp.body.decode("utf-8"))
        except Exception as exc:
            raise ProviderError(f"invalid JSON from Anthropic: {type(exc).__name__}") from exc

        content_blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

        usage_data = data.get("usage") or {}
        p_tokens = usage_data.get("input_tokens") or 0
        c_tokens = usage_data.get("output_tokens") or 0
        usage = Usage(prompt_tokens=p_tokens, completion_tokens=c_tokens) if (p_tokens or c_tokens) else estimate_usage(request.messages, text)

        return ProviderResponse(text=text, usage=usage, model=self._model)
