"""Gateway seam: the errors, the provider interface and the request/response it exchanges.

A provider is the thing that actually produces text (the fake provider, or one OpenAI-compatible
HTTP adapter). The gateway in front of it applies policy; a provider never sees a principal, an
app profile or a cache.
"""

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from insights.contracts.enums import Purpose
from insights.contracts.gateway import Message, Usage


class GatewayError(Exception):
    """Base for everything the gateway refuses or fails at."""


class PurposeDisabledError(GatewayError):
    """The app profile does not enable this purpose."""


class PromptPolicyError(GatewayError):
    """A prompt broke a rule. Subclasses never repeat the offending text."""


class PrincipalInPromptError(PromptPolicyError):
    """An identifier of the caller was about to be sent to a model."""


class RowsNotAllowedError(PromptPolicyError):
    """Result rows were flagged for a purpose that may not receive them."""


class UnflaggedRowsError(PromptPolicyError):
    """A prompt carries values from this run's result rows but is not flagged `contains_rows`."""


class ResponseSchemaError(GatewayError):
    """The model's answer is not valid JSON or does not match the requested schema."""


class ProviderError(GatewayError):
    """The provider failed. The message names the kind of failure, never the prompt or the body."""


class ModelUnavailableError(ProviderError):
    """No model is configured (provider "none"). The default build raises this for every call, so a
    data question ends as `failed / model_unavailable`, not a fabricated or replayed answer."""


class FakeProviderError(ProviderError):
    """Base for fake-provider refusals."""


class UnknownFakeRequestError(FakeProviderError):
    """No fixture matches. The fake provider never invents an answer."""


class AmbiguousFakeRequestError(FakeProviderError):
    """More than one fixture matches. The fake provider never picks one silently."""


class FixtureError(ValueError):
    """A fake-provider fixture file is unreadable or invalid."""


@dataclass(frozen=True)
class ProviderRequest:
    model: str
    messages: tuple[Message, ...]
    purpose: Purpose
    temperature: float
    max_tokens: int
    response_schema: dict[str, Any] | None
    no_store: bool


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    usage: Usage
    model: str


class Provider(Protocol):
    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


def canonical_messages_sha256(messages: Sequence[Message]) -> str:
    """Hash of role and content only, so the same words always hash the same."""
    canonical = json.dumps([[m.role, m.content] for m in messages], ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def estimate_usage(messages: Sequence[Message], text: str) -> Usage:
    """About four characters per token. Used only when a provider reports no usage."""
    prompt_chars = sum(len(m.content) + 4 for m in messages)
    return Usage(
        prompt_tokens=max(1, math.ceil(prompt_chars / 4)),
        completion_tokens=max(1, math.ceil(len(text) / 4)),
    )
