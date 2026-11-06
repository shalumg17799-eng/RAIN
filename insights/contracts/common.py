"""Base class and scalar types shared by every contract.

Every contract forbids unknown fields. That single setting is what keeps a stray `principal`,
`app_profile` or `rows` key out of a request body, an event, an audit record or run state.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class Contract(BaseModel):
    """Immutable, strict-keyed base model."""

    model_config = ConfigDict(extra="forbid", frozen=True)


SemVer = Annotated[str, StringConstraints(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")]
"""MAJOR.MINOR.PATCH only. No pre-release or build suffixes."""

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,62}$")]
"""Step ids, labels, role names, source ids."""

SkillName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{1,62}$")]

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

SqlIdentifier = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$")
]
"""A table or column name, optionally schema- or catalog-qualified."""

JsonScalar = str | int | float | bool | None


class SecretRef(Contract):
    """A secret by reference: the name of an environment variable, never a value."""

    env: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{1,63}$")]
