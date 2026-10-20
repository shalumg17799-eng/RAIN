"""The authenticated caller. Server-side only.

A Principal is built from the Authorization header by the API layer (S10). It is never accepted in a
request body and never placed in a prompt: `prompt_forbidden_values` lists what the gateway must
refuse to see in any message (S4).
"""

from pydantic import Field

from insights.contracts.common import Contract, Identifier, Sha256Hex


class Principal(Contract):
    subject: str
    tenant: str
    roles: tuple[Identifier, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)
    """Claims that row filters may use, for example `branch_id`. Never sent to a prompt."""
    entitlement_digest: Sha256Hex
    """Digest of the entitlements in force. Part of every cache key (no cross-principal cache)."""
    token_ref: str | None = None
    """A reference to the user's token held by the identity layer. Never the token itself."""

    def prompt_forbidden_values(self) -> tuple[str, ...]:
        values = [self.subject, self.tenant, self.token_ref or "", *self.attributes.values()]
        return tuple(v for v in values if v)
