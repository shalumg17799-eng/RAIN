"""Native Anthropic Messages API provider for the governed LLM gateway."""

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from insights.contracts.gateway import Usage
from insights.gateway.base import ProviderError, ProviderRequest, ProviderResponse, estimate_usage
from insights.gateway.openai_compat import Transport, TransportResponse, UrllibTransport

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


def _schema_directive(schema: dict[str, Any]) -> str:
    required = schema.get("required")
    keys = ", ".join(str(key) for key in required) if required else "the fields in the schema below"
    return (
        "Respond with exactly one JSON object and nothing else. Use these keys exactly: "
        f"{keys}. The object must satisfy this JSON Schema:\n"
        f"{json.dumps(schema, separators=(',', ':'))}"
    )


class AnthropicProvider:
    """Calls Anthropic's Messages API; response schemas are enforced by the gateway."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("base_url must be an http(s) URL with a host")
        if parts.username or parts.password:
            raise ValueError("base_url must not contain credentials")
        if not api_key:
            raise ValueError("Anthropic API key is required")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._transport = transport or UrllibTransport()

    def __repr__(self) -> str:
        return f"AnthropicProvider(base_url={self._base_url!r}, key={'set' if self._api_key else 'none'})"

    __str__ = __repr__

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        system = [message.content for message in request.messages if message.role == "system"]
        if request.response_schema is not None:
            system.append(_schema_directive(request.response_schema))
        messages = [
            {"role": message.role, "content": message.content}
            for message in request.messages
            if message.role != "system"
        ]
        payload: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
            "temperature": request.temperature,
        }
        if system:
            payload["system"] = "\n\n".join(system)

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        if request.no_store:
            headers["Cache-Control"] = "no-store"
        try:
            response: TransportResponse = self._transport.post(
                f"{self._base_url}/messages",
                headers,
                json.dumps(payload).encode("utf-8"),
                self._timeout_s,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"transport failed: {type(exc).__name__}") from exc
        if response.status != 200:
            raise ProviderError(f"Anthropic provider returned HTTP {response.status}")

        try:
            data = json.loads(response.body)
            text = "\n".join(
                block["text"]
                for block in data["content"]
                if block.get("type") == "text" and isinstance(block.get("text"), str)
            )
        except (ValueError, KeyError, TypeError):
            raise ProviderError("Anthropic response is not a Messages API response") from None
        if not text:
            raise ProviderError("Anthropic response has no text content")

        raw_usage = data.get("usage", {})
        try:
            usage = Usage(
                prompt_tokens=int(raw_usage["input_tokens"]),
                completion_tokens=int(raw_usage["output_tokens"]),
            )
        except (KeyError, TypeError, ValueError):
            usage = estimate_usage(request.messages, text)
        model = data.get("model") if isinstance(data.get("model"), str) else request.model
        return ProviderResponse(text=text, usage=usage, model=model)
