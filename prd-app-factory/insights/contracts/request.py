"""POST /v1/apps/{app_id}/ask request body.

Caller identity comes from the Authorization header and the app profile from the server. Neither
is a field here, and unknown fields are rejected, so neither can arrive in the body.
"""

from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from insights.contracts.common import Contract

MAX_QUERY_CHARS = 10_000
"""Hard payload cap. The router applies the (smaller) per-app limit and decides what to do."""

ContextValue = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:/ -]{1,64}$")]
"""Short label text only. Context reaches prompts as hints, so no free text."""


class AskContext(Contract):
    market: ContextValue | None = None
    product: ContextValue | None = None
    domain: ContextValue | None = None
    component: ContextValue | None = None
    variant: ContextValue | None = None


class AskOptions(Contract):
    """Callers may only tighten limits: effective value = min(request, app profile, agent)."""

    max_refines: int | None = Field(default=None, ge=0, le=5)
    timeout_ms: int | None = Field(default=None, ge=100, le=300_000)
    stream: bool = False


class AskRequest(Contract):
    request_id: UUID
    query: Annotated[str, StringConstraints(max_length=MAX_QUERY_CHARS)]
    context: AskContext = AskContext()
    conversation_id: UUID | None = None
    options: AskOptions = AskOptions()
