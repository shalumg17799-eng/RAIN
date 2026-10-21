"""The one HTTP adapter: any OpenAI-compatible /chat/completions endpoint.

Works with a local Ollama today (no key needed) and with LiteLLM or a hosted provider later: the
endpoint, model and optional key all come from configuration. The key is only ever sent as a bearer
token; it is kept out of repr, logs and error messages, and error bodies are never echoed because a
server may repeat the prompt back.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from insights.contracts.gateway import Usage
from insights.gateway.base import ProviderError, ProviderRequest, ProviderResponse, estimate_usage

StructuredOutput = Literal["json_schema", "json_object", "none"]


@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: bytes


class Transport(Protocol):
    def post(
        self, url: str, headers: Mapping[str, str], body: bytes, timeout_s: float
    ) -> TransportResponse: ...


class UrllibTransport:
    """Standard-library HTTP. Only http and https URLs are ever opened."""

    def post(
        self, url: str, headers: Mapping[str, str], body: bytes, timeout_s: float
    ) -> TransportResponse:
        if urlsplit(url).scheme not in ("http", "https"):
            raise ProviderError("unsupported URL scheme (only http and https)")
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
                return TransportResponse(response.status, response.read())
        except urllib.error.HTTPError as exc:
            # keep the body for the caller to INSPECT (e.g. a known compatibility quirk); the
            # provider never puts it into an error message, so the prompt is never echoed back.
            try:
                return TransportResponse(exc.code, exc.read())
            except Exception:
                return TransportResponse(exc.code, b"")
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise ProviderError(f"transport failed: {type(exc).__name__}") from exc


def _schema_directive(schema: dict[str, Any]) -> str:
    """A prompt directive naming the exact JSON shape, for endpoints that cannot enforce a schema
    (structured output "none"). It lists the required keys and embeds the schema so the model uses
    the right field names and returns one bare object (no markdown fences, no prose)."""
    required = schema.get("required") if isinstance(schema, dict) else None
    keys = ", ".join(str(k) for k in required) if required else "the fields in the schema below"
    return (
        "Respond with EXACTLY ONE JSON object and nothing else: no markdown code fences, no prose "
        f"before or after. Use these keys exactly: {keys}. The object must satisfy this JSON "
        f"Schema:\n{json.dumps(schema, separators=(',', ':'))}"
    )


def _rejects_temperature(body: bytes) -> bool:
    """True when a 400 body says the model does not accept `temperature` (an Anthropic quirk for
    some models). Checked by substring only; the body is never echoed in an error."""
    try:
        text = body.decode("utf-8", "replace").lower()
    except Exception:
        return False
    return "temperature" in text and (
        "deprecat" in text or "unsupported" in text or "not supported" in text
    )


def _validate_base_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("base_url must be an http(s) URL with a host")
    if parts.username or parts.password:
        raise ValueError("base_url must not contain credentials; use the API key setting")
    return url.rstrip("/")


class OpenAICompatProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_s: float = 60.0,
        structured_output: StructuredOutput = "json_schema",
        transport: Transport | None = None,
    ) -> None:
        self._base_url = _validate_base_url(base_url)
        self._api_key = api_key or None
        self._timeout_s = timeout_s
        self._structured = structured_output
        self._transport: Transport = transport or UrllibTransport()

    def __repr__(self) -> str:
        key = "set" if self._api_key else "none"
        return f"OpenAICompatProvider(base_url={self._base_url!r}, key={key})"

    __str__ = __repr__

    def _payload(self, request: ProviderRequest, *, with_temperature: bool) -> dict[str, Any]:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        if with_temperature:
            payload["temperature"] = request.temperature
        if request.response_schema is not None and self._structured == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": request.response_schema,
                    "strict": True,
                },
            }
        elif request.response_schema is not None and self._structured == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif request.response_schema is not None:  # "none": the endpoint cannot enforce the schema,
            # so the model is TOLD the exact shape in the prompt (a system directive is merged in).
            directive = _schema_directive(request.response_schema)
            messages.append({"role": "system", "content": directive})
        return payload

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if request.no_store:
            headers["Cache-Control"] = "no-store"

        def send(with_temperature: bool) -> TransportResponse:
            body = json.dumps(self._payload(request, with_temperature=with_temperature))
            try:
                return self._transport.post(
                    f"{self._base_url}/chat/completions",
                    headers,
                    body.encode("utf-8"),
                    self._timeout_s,
                )
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(f"transport failed: {type(exc).__name__}") from exc

        response = send(with_temperature=True)
        # Anthropic (and some newer models) reject `temperature`; retry once without it. The error
        # body is inspected only for this known quirk and is never surfaced in an exception.
        if response.status == 400 and _rejects_temperature(response.body):
            response = send(with_temperature=False)

        if response.status != 200:
            raise ProviderError(f"provider returned HTTP {response.status}")
        return self._parse(response.body, request)

    @staticmethod
    def _parse(body: bytes, request: ProviderRequest) -> ProviderResponse:
        try:
            data = json.loads(body)
            text = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("provider response is not a chat completion") from None
        if not isinstance(text, str):
            raise ProviderError("provider response has no text content")
        usage_raw = data.get("usage") if isinstance(data, dict) else None
        try:
            usage = Usage(
                prompt_tokens=int(usage_raw["prompt_tokens"]),
                completion_tokens=int(usage_raw["completion_tokens"]),
            )
        except (KeyError, TypeError, ValueError):
            usage = estimate_usage(request.messages, text)
        model = data.get("model") if isinstance(data.get("model"), str) else request.model
        try:
            finish_reason = data["choices"][0].get("finish_reason")
        except (KeyError, IndexError, TypeError):
            finish_reason = None
        return ProviderResponse(
            text=text, usage=usage, model=model, truncated=finish_reason == "length"
        )
