"""The default provider: none. It has no model, so every call raises `ModelUnavailableError`.

This is what a default run uses. A data question therefore ends honestly as
`failed / model_unavailable`; nothing is replayed or invented. Configure a real OpenAI-compatible
endpoint through the environment (see the README) to replace it.
"""

from insights.gateway.base import ModelUnavailableError, ProviderRequest, ProviderResponse


class NoModelProvider:
    """A provider that answers nothing. `complete` always raises, by design."""

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        raise ModelUnavailableError("no model is configured (INSIGHTS_LLM_PROVIDER=none)")
