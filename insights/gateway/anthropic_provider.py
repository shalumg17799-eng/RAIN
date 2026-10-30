"""Native Anthropic Messages API provider for the governed LLM gateway."""

import json
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from insights.contracts.gateway import Usage
from insights.gateway.base import ProviderError, ProviderRequest, ProviderResponse, estimate_usage
from insights.gateway.openai_compat import Transport, TransportResponse, UrllibTransport

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
# Rate limits, overload and transient server/transport errors are retried with backoff: a
# completion request is pure, so re-sending it is always safe. Anything else fails immediately.
RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504, 529})
_RETRY_SLEEPS = (10.0, 30.0, 60.0)  # module-level so tests can stub the backoff


def _error_kind(body: bytes) -> str:
    """The error *type* from an Anthropic error body (e.g. rate_limit_error, overloaded_error).
    Only this short identifier is surfaced; the body itself is never echoed into messages."""
    try:
        kind = json.loads(body).get("error", {}).get("type")
        return str(kind) if kind else ""
    except Exception:
        return ""


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
        if request.response_schema is not None:
            payload["tools"] = [
                {
                    "name": "submit_structured_response",
                    "description": "Return the requested structured artifact. This tool does not execute actions.",
                    "input_schema": request.response_schema,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": "submit_structured_response"}

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        if request.no_store:
            headers["Cache-Control"] = "no-store"
        body = json.dumps(payload).encode("utf-8")
        response: TransportResponse | None = None
        for attempt in range(len(_RETRY_SLEEPS) + 1):
            try:
                response = self._transport.post(
                    f"{self._base_url}/messages", headers, body, self._timeout_s
                )
            except ProviderError:
                if attempt == len(_RETRY_SLEEPS):
                    raise
                time.sleep(_RETRY_SLEEPS[attempt])
                continue
            except Exception as exc:
                raise ProviderError(f"transport failed: {type(exc).__name__}") from exc
            if response.status == 200:
                break
            if response.status not in RETRYABLE_STATUS or attempt == len(_RETRY_SLEEPS):
                kind = _error_kind(response.body)
                raise ProviderError(
                    f"Anthropic provider returned HTTP {response.status}"
                    + (f" ({kind})" if kind else "")
                    + (f" after {attempt + 1} attempts" if attempt else "")
                )
            time.sleep(_RETRY_SLEEPS[attempt])
        assert response is not None  # the loop either breaks with a 200 or raises

        try:
            data = json.loads(response.body)
            tool_inputs = [
                block["input"]
                for block in data["content"]
                if block.get("type") == "tool_use"
                and block.get("name") == "submit_structured_response"
                and isinstance(block.get("input"), dict)
            ]
            if request.response_schema is not None and tool_inputs:
                text = json.dumps(tool_inputs[0], ensure_ascii=False)
            else:
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
        return ProviderResponse(
            text=text, usage=usage, model=model,
            truncated=data.get("stop_reason") == "max_tokens",
        )
