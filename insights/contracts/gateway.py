"""LLM seam types: gateway.complete(messages, purpose, ctx, response_schema=None) (report 5.8).

The call signature is fixed by the spec, so "this prompt contains rows" travels on the message
(`contains_rows`). The gateway marks such a call no-store and refuses it for any purpose that may
not see rows (enforced in S4).
"""

from typing import Any, Literal

from pydantic import Field

from insights.contracts.common import Contract


class Message(Contract):
    role: Literal["system", "user", "assistant"]
    content: str
    contains_rows: bool = False


class Usage(Contract):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class CompletionResult(Contract):
    """`content` is text, or the validated object when a response_schema was given."""

    content: str | dict[str, Any]
    usage: Usage
    model: str
    cache_hit: bool = False
    truncated: bool = False
    """The provider stopped at max_tokens: the content is incomplete, not malformed."""
