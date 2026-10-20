"""Gateway configuration from the environment, and the factory that builds a gateway from it.

INSIGHTS_LLM_PROVIDER           none (default) | openai_compat
INSIGHTS_LLM_BASE_URL           e.g. http://localhost:11434/v1 for a local Ollama
INSIGHTS_LLM_MODEL              model id used for every model group unless pinned below
INSIGHTS_LLM_MODEL_<GROUP>      pin one group's model, e.g. INSIGHTS_LLM_MODEL_STRONG
INSIGHTS_LLM_BASE_URL_<GROUP>   send one group to its own OpenAI-compatible endpoint
INSIGHTS_LLM_API_KEY_<GROUP>    the key for that group's endpoint (optional)
INSIGHTS_LLM_API_KEY            optional; a local server needs none
INSIGHTS_LLM_TIMEOUT_S          default 60
INSIGHTS_LLM_STRUCTURED_OUTPUT  json_schema (default) | json_object | none
INSIGHTS_LLM_CACHE_TTL_S        exact-match cache TTL in seconds; default 300, 0 disables it

The default is "none": no model, so every call raises ModelUnavailableError and a data question
ends as failed / model_unavailable. There is no fake or replay path in a default run; the fake
provider lives only under tests/ as a test double. Set INSIGHTS_LLM_PROVIDER=openai_compat with a
base URL and model to use a real endpoint.

Per-group providers (DIF-38): a model group (`fast`, `strong`, ...) can be sent to its own
OpenAI-compatible endpoint with INSIGHTS_LLM_BASE_URL_<GROUP> (and an optional key); groups without
their own endpoint use the top-level one. Every endpoint speaks the same OpenAI-compatible protocol,
so a LiteLLM proxy can sit behind any base URL unchanged -- deploying LiteLLM is a later step.
"""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from insights.gateway.base import Provider
from insights.gateway.cache import InMemoryExactCache
from insights.gateway.gateway import LLMGateway
from insights.gateway.anthropic_provider import AnthropicProvider
from insights.gateway.none_provider import NoModelProvider
from insights.gateway.openai_compat import OpenAICompatProvider

_PREFIX = "INSIGHTS_LLM_"
_MODEL_PREFIX = f"{_PREFIX}MODEL_"
_BASE_URL_PREFIX = f"{_PREFIX}BASE_URL_"
_API_KEY_PREFIX = f"{_PREFIX}API_KEY_"

DEFAULT_CACHE_TTL_S = 300
"""The exact-match cache is ON by default: per caller, never across principals, never for rows."""


class ConfigError(ValueError):
    """The gateway configuration is invalid."""


class GroupEndpoint(BaseModel):
    """One model group's own OpenAI-compatible endpoint (DIF-38)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    api_key: SecretStr | None = None


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["none", "openai_compat", "anthropic"] = "none"
    base_url: str | None = None
    api_key: SecretStr | None = None
    default_model: str | None = None
    model_overrides: dict[str, str] = Field(default_factory=dict)
    group_endpoints: dict[str, GroupEndpoint] = Field(default_factory=dict)
    timeout_s: float = Field(default=60.0, gt=0)
    structured_output: Literal["json_schema", "json_object", "none"] = "json_schema"
    cache_ttl_seconds: int = Field(default=DEFAULT_CACHE_TTL_S, ge=0)

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "GatewayConfig":
        def get(name: str) -> str | None:
            value = environ.get(f"{_PREFIX}{name}", "").strip()
            return value or None

        def by_group(prefix: str) -> dict[str, str]:
            return {
                key[len(prefix) :].lower(): value.strip()
                for key, value in environ.items()
                if key.startswith(prefix) and value.strip()
            }

        base_url_overrides = by_group(_BASE_URL_PREFIX)
        api_key_overrides = by_group(_API_KEY_PREFIX)
        group_endpoints = {
            group: {"base_url": base_url, "api_key": api_key_overrides.get(group)}
            for group, base_url in base_url_overrides.items()
        }
        provider = get("PROVIDER") or "none"
        api_key = get("API_KEY")
        if provider == "anthropic" and api_key is None:
            api_key = environ.get("ANTHROPIC_API_KEY", "").strip() or None
        raw: dict[str, object] = {
            "provider": provider,
            "base_url": get("BASE_URL"),
            "api_key": api_key,
            "default_model": get("MODEL"),
            "model_overrides": by_group(_MODEL_PREFIX),
            "group_endpoints": group_endpoints,
        }
        for field, name in (
            ("timeout_s", "TIMEOUT_S"),
            ("structured_output", "STRUCTURED_OUTPUT"),
            ("cache_ttl_seconds", "CACHE_TTL_S"),
        ):
            if get(name) is not None:
                raw[field] = get(name)
        try:
            config = cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(f"invalid gateway configuration: {exc.errors()[0]['loc']}") from exc
        if config.provider == "openai_compat" and not (config.base_url and config.default_model):
            raise ConfigError("openai_compat needs INSIGHTS_LLM_BASE_URL and INSIGHTS_LLM_MODEL")
        if config.provider == "anthropic" and not (config.api_key and config.default_model):
            raise ConfigError("anthropic needs ANTHROPIC_API_KEY and INSIGHTS_LLM_MODEL")
        if config.provider == "anthropic" and config.group_endpoints:
            raise ConfigError("per-group endpoints are only supported by openai_compat")
        for group in config.group_endpoints:
            if group not in config.model_overrides and config.default_model is None:
                raise ConfigError(
                    f"group {group!r} has its own endpoint but no model: set "
                    f"INSIGHTS_LLM_MODEL_{group.upper()} or INSIGHTS_LLM_MODEL"
                )
        return config

    def model_for(self, group: str) -> str:
        if group in self.model_overrides:
            return self.model_overrides[group]
        if group in self.group_endpoints:
            if self.default_model is None:
                raise ConfigError(f"no model configured for group {group!r}")
            return self.default_model
        if self.provider == "none":
            return "none"
        if self.default_model is None:
            raise ConfigError(f"no model configured for group {group!r}")
        return self.default_model


def _openai_provider(
    config: GatewayConfig, base_url: str, api_key: SecretStr | None
) -> OpenAICompatProvider:
    try:
        return OpenAICompatProvider(
            base_url=base_url,
            api_key=api_key.get_secret_value() if api_key else None,
            timeout_s=config.timeout_s,
            structured_output=config.structured_output,
        )
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def _anthropic_provider(config: GatewayConfig) -> AnthropicProvider:
    if config.api_key is None:
        raise ConfigError("Anthropic API key is required")
    try:
        return AnthropicProvider(
            base_url=config.base_url or "https://api.anthropic.com/v1",
            api_key=config.api_key.get_secret_value(),
            timeout_s=config.timeout_s,
        )
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def build_gateway(config: GatewayConfig) -> LLMGateway:
    """The default (provider "none") yields a gateway whose every call raises ModelUnavailableError.
    There is no fake or replay path here: the fake provider is a test double under tests/ and is
    injected directly by tests, never built from configuration.

    Per-group endpoints (DIF-38) each build their own OpenAI-compatible provider; the gateway routes
    a call to the provider for its purpose's model group, falling back to the top-level provider."""
    default_provider: Provider
    if config.provider == "openai_compat":
        default_provider = _openai_provider(config, config.base_url or "", config.api_key)
    elif config.provider == "anthropic":
        default_provider = _anthropic_provider(config)
    else:
        default_provider = NoModelProvider()
    providers: dict[str, Provider] = {
        group: _openai_provider(config, endpoint.base_url, endpoint.api_key)
        for group, endpoint in config.group_endpoints.items()
    }
    cache = (
        InMemoryExactCache(ttl_seconds=config.cache_ttl_seconds)
        if config.cache_ttl_seconds
        else None
    )
    return LLMGateway(
        default_provider, model_for=config.model_for, cache=cache, providers=providers
    )
