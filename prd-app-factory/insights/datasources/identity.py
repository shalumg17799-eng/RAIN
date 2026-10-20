"""Identity modes: how a caller's identity reaches the data platform (design report 5.4, layer 3).

    per_user                          the target. The platform sees the caller's role and claims and
                                      applies its own grants, row-level security and masks.
    service_principal_with_views      one service identity; each role reads only its own views, with
                                      the row filter and masks baked in. Needs a recorded risk.
    service_principal_with_predicates the application injects row filters into the SQL itself. The
                                      weakest: a rewrite bug is a leak. Needs a recorded risk.

A Binding says what the adapter must do inside the transaction before it runs the query. It is
built on the server from the Principal and the profile; none of it comes from the request.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from sqlglot import exp

from insights.catalog.entitlements import (
    default_schema_of,
    effective_role,
    role_tables,
    source_schemas,
)
from insights.contracts.enums import IdentityMode
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile
from insights.datasources import naming

_ATTRIBUTE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
_ATTRIBUTE_VALUE = re.compile(r"^[A-Za-z0-9_.@:-]{1,64}$")
_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")
MAX_SUBJECT = 256


class IdentityError(ValueError):
    """The caller cannot be bound to this app (no role, unusable claim). Fail closed."""


@dataclass(frozen=True)
class Binding:
    mode: IdentityMode
    role: str | None
    """Database role for `SET LOCAL ROLE`."""
    search_path: tuple[str, ...]
    settings: Mapping[str, str] = field(default_factory=dict)
    """Session variables for this transaction only (`set_config(name, value, true)`)."""
    row_predicates: Mapping[str, str] = field(default_factory=dict)
    """Mode C only: table -> SQL condition that L1 injects into the checked query."""


class IdentityStrategy(Protocol):
    mode: IdentityMode

    def bind(self, principal: Principal, app: AppProfile) -> Binding: ...


def _require_role(principal: Principal, app: AppProfile) -> str:
    role = effective_role(principal, app)
    if role is None:
        raise IdentityError("the principal holds no role defined for this app")
    return role


def _settings(principal: Principal) -> dict[str, str]:
    if not principal.subject or len(principal.subject) > MAX_SUBJECT:
        raise IdentityError("the principal subject is empty or too long")
    settings = {naming.guc("subject"): principal.subject}
    for name, value in principal.attributes.items():
        if not _ATTRIBUTE_NAME.match(name) or not _ATTRIBUTE_VALUE.match(value):
            raise IdentityError(f"principal attribute {name!r} has an unusable name or value")
        settings[naming.guc(name)] = value
    return settings


def render_predicate(template: str, attributes: Mapping[str, str], dialect: str) -> str:
    """Fill `{attr}` placeholders with escaped SQL literals. A missing claim is an error."""

    def literal(match: re.Match[str]) -> str:
        name = match.group(1)
        value = attributes.get(name)
        if value is None or not _ATTRIBUTE_VALUE.match(value):
            raise IdentityError(f"row filter needs attribute {name!r}, which the principal lacks")
        return exp.Literal.string(value).sql(dialect=dialect)

    return _PLACEHOLDER.sub(literal, template)


class PerUser:
    mode = IdentityMode.PER_USER

    def bind(self, principal: Principal, app: AppProfile) -> Binding:
        role = _require_role(principal, app)
        # the masked-view schema first (so a role's masked views shadow the base tables), then every
        # base schema of the source. A single-schema source keeps its old two-entry path; NFCU's 13
        # schemas all go on so bare table names resolve. The role's own USAGE/SELECT grants -- not
        # the search path -- are the authority, so listing a schema the role cannot use is harmless.
        base = source_schemas(app) or (default_schema_of(app) or "public",)
        return Binding(
            mode=self.mode,
            role=naming.per_user_role(role),
            search_path=(naming.per_user_view_schema(role), *base),
            settings=_settings(principal),
        )


class ServicePrincipalWithViews:
    mode = IdentityMode.SERVICE_PRINCIPAL_WITH_VIEWS

    def bind(self, principal: Principal, app: AppProfile) -> Binding:
        role = _require_role(principal, app)
        return Binding(
            mode=self.mode,
            role=naming.views_role(role),
            search_path=(naming.views_schema(role),),
            settings=_settings(principal),
        )


class ServicePrincipalWithPredicates:
    mode = IdentityMode.SERVICE_PRINCIPAL_WITH_PREDICATES

    def bind(self, principal: Principal, app: AppProfile) -> Binding:
        role = _require_role(principal, app)
        _settings(principal)  # validates the subject and attributes even though none are sent
        dialect = app.dialect.value
        predicates = {
            table: render_predicate(access.row_filter, principal.attributes, dialect)
            for table, access in role_tables(app, role).items()
            if access.row_filter
        }
        schema = default_schema_of(app) or "public"
        return Binding(
            mode=self.mode,
            role=naming.PREDICATE_ROLE,
            search_path=(schema,),
            row_predicates=predicates,
        )


_STRATEGIES: dict[IdentityMode, IdentityStrategy] = {
    IdentityMode.PER_USER: PerUser(),
    IdentityMode.SERVICE_PRINCIPAL_WITH_VIEWS: ServicePrincipalWithViews(),
    IdentityMode.SERVICE_PRINCIPAL_WITH_PREDICATES: ServicePrincipalWithPredicates(),
}


def strategy_for(mode: IdentityMode) -> IdentityStrategy:
    return _STRATEGIES[mode]


def bind_identity(
    principal: Principal, app: AppProfile, mode: IdentityMode | None = None
) -> Binding:
    """Bind with the app's configured mode (or an explicit one, for tests and the fallback)."""
    return strategy_for(mode or app.identity.mode).bind(principal, app)
