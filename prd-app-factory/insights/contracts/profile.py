"""Application profile: apps/<app>/app.yaml. Server-side only, never in a request or a prompt.

Secrets are by reference (`{env: NAME}`) and the type system enforces it: a field typed SecretRef
cannot be given a plain string. A profile marked `status: stub` is never loaded.
"""

import hashlib
import json
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import AfterValidator, Field, ValidationError, model_validator

from insights.contracts.common import (
    Contract,
    Identifier,
    SecretRef,
    SemVer,
    Sha256Hex,
    SkillName,
    SqlIdentifier,
)
from insights.contracts.enums import Dialect, IdentityMode, Intent, MaskKind, PathName, Purpose
from insights.contracts.request import MAX_QUERY_CHARS
from insights.yamlio import load_yaml


def _relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
        raise ValueError("must be a relative path inside the app folder (no '..', no drive)")
    return value


RelativePath = Annotated[str, AfterValidator(_relative_path)]


class ProfileError(ValueError):
    """The profile file is missing, a stub, or invalid."""


class AgentRef(Contract):
    name: SkillName
    version: SemVer


class RouterThresholds(Contract):
    embedding_accept: float = Field(default=0.80, ge=0.0, le=1.0)
    embedding_margin: float = Field(default=0.05, ge=0.0, le=1.0)
    llm_accept: float = Field(default=0.60, ge=0.0, le=1.0)


class RouterConfig(Contract):
    exemplars: dict[Intent, tuple[str, ...]]
    thresholds: RouterThresholds = RouterThresholds()
    unsure_policy: Literal["needs_clarification", "out_of_scope"] = "needs_clarification"
    max_query_chars: int = Field(default=2000, ge=1, le=MAX_QUERY_CHARS)
    path_preference: PathName = PathName.BYPASS
    """The retrieval path the router prefers. The sliver step probes it and may fall back."""


class DataSource(Contract):
    """One data source. Credentials are references only."""

    id: Identifier
    kind: Literal["postgres", "databricks"]
    host: str
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str | None = None
    default_schema: str | None = None
    schemas: tuple[SqlIdentifier, ...] = ()
    """Extra schemas on the search path (a multi-schema source, e.g. NFCU's 13). Bare table names
    must be unique across them. Empty means the single `default_schema`."""
    http_path: str | None = None
    user: SecretRef | None = None
    password: SecretRef | None = None
    token: SecretRef | None = None

    @model_validator(mode="after")
    def _required_per_kind(self) -> "DataSource":
        if self.kind == "postgres":
            missing = [
                name
                for name in ("port", "database", "user", "password")
                if getattr(self, name) is None
            ]
        else:
            missing = [name for name in ("http_path", "token") if getattr(self, name) is None]
        if missing:
            raise ValueError(f"{self.kind} data source needs: {', '.join(missing)}")
        return self


class CatalogSource(Contract):
    kind: Literal["snapshot"] = "snapshot"
    path: RelativePath


class IdentityConfig(Contract):
    mode: IdentityMode
    fallback: IdentityMode | None = None
    risk_acceptance: str | None = None
    """Reference to the recorded risk acceptance. Required for any mode other than per_user."""

    @model_validator(mode="after")
    def _risk_is_recorded(self) -> "IdentityConfig":
        if self.mode is not IdentityMode.PER_USER and not self.risk_acceptance:
            raise ValueError(f"{self.mode.value} needs a recorded risk_acceptance reference")
        if self.fallback is self.mode:
            raise ValueError("fallback must differ from mode")
        return self


class TableAccess(Contract):
    columns: tuple[SqlIdentifier, ...] | Literal["*"]
    row_filter: str | None = None
    """Documents the row filter the platform enforces (RLS or Unity Catalog). Not the authority."""
    masks: dict[SqlIdentifier, MaskKind] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _filter_is_a_plain_condition(self) -> "TableAccess":
        text = self.row_filter
        if text is not None and (
            len(text) > 200 or any(t in text for t in (";", "--", "/*", "*/"))
        ):
            raise ValueError("row_filter must be one short condition (no ';' or comments)")
        return self

    @model_validator(mode="after")
    def _masks_target_visible_columns(self) -> "TableAccess":
        if self.columns != "*":
            hidden = set(self.masks) - set(self.columns)
            if hidden:
                raise ValueError(f"masks on columns the role cannot see: {sorted(hidden)}")
        return self


class RoleEntitlements(Contract):
    tables: dict[SqlIdentifier, TableAccess] = Field(min_length=1)


class ModelPolicy(Contract):
    """Per-purpose model policy. `model_group` is a logical name the gateway resolves."""

    enabled: bool
    model_group: Identifier
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(ge=1, le=32_000)
    rows_in_prompt: Literal["never", "masked_sample"] = "never"
    max_sample_rows: int = Field(default=0, ge=0, le=20)

    @model_validator(mode="after")
    def _sample_rows_agree(self) -> "ModelPolicy":
        if (self.rows_in_prompt == "never") != (self.max_sample_rows == 0):
            raise ValueError("max_sample_rows must be 0 exactly when rows_in_prompt is 'never'")
        return self


class Calendar(Contract):
    timezone: str = "UTC"
    week_starts_on: Literal["monday", "sunday"] = "monday"
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    today: date | None = None
    """A fixed clock for synthetic apps whose data must stay reproducible. None = the real clock."""

    @model_validator(mode="after")
    def _known_timezone(self) -> "Calendar":
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {self.timezone!r}") from exc
        return self


class Limits(Contract):
    max_rows: int = Field(ge=1, le=1_000_000)
    statement_timeout_ms: int = Field(ge=100, le=600_000)
    max_estimated_cost: float | None = Field(default=None, gt=0)
    max_estimated_rows: int | None = Field(default=None, ge=1)
    max_refines: int = Field(default=2, ge=0, le=5)
    max_tokens: int = Field(ge=1)
    deadline_ms: int = Field(ge=100, le=600_000)


class SqlVisibility(Contract):
    default: bool = False
    roles: dict[Identifier, bool] = Field(default_factory=dict)

    def visible_to(self, roles: tuple[str, ...]) -> bool:
        """True if any of the caller's roles grants it, else the default."""
        grants = [self.roles[role] for role in roles if role in self.roles]
        return any(grants) if grants else self.default


class AppProfileRef(Contract):
    """What run state keeps instead of a copy of the profile (reproducibility, report R7)."""

    id: Identifier
    version: SemVer
    dialect: Dialect
    content_sha256: Sha256Hex


class AppProfile(Contract):
    id: Identifier
    version: SemVer
    status: Literal["active"] = "active"
    description: str = ""
    dialect: Dialect
    agent: AgentRef
    allowed_intents: tuple[Intent, ...] = Field(min_length=1)
    multi_turn: bool = False
    router: RouterConfig
    datasources: tuple[DataSource, ...] = Field(min_length=1)
    catalog: CatalogSource
    glossary_path: RelativePath
    join_hints_path: RelativePath | None = None
    examples_path: RelativePath | None = None
    """Reviewed question-to-SQL pairs the query generator may show as examples."""
    identity: IdentityConfig
    roles: dict[Identifier, RoleEntitlements] = Field(min_length=1)
    model_policy: dict[Purpose, ModelPolicy]
    calendar: Calendar = Calendar()
    limits: Limits
    confidence_threshold: float = Field(ge=0.0, le=1.0)
    sql_visibility: SqlVisibility = SqlVisibility()

    @model_validator(mode="after")
    def _consistent(self) -> "AppProfile":
        if Intent.DATA_QUERY not in self.allowed_intents:
            raise ValueError("allowed_intents must include data_query")
        if len(set(self.allowed_intents)) != len(self.allowed_intents):
            raise ValueError("allowed_intents must be unique")
        stray = set(self.router.exemplars) - set(self.allowed_intents)
        if stray:
            raise ValueError(f"router exemplars for intents that are not allowed: {sorted(stray)}")
        ids = [source.id for source in self.datasources]
        if len(set(ids)) != len(ids):
            raise ValueError("datasource ids must be unique")
        wrong = [s.id for s in self.datasources if s.kind != self.dialect.value]
        if wrong:
            raise ValueError(f"datasources {wrong} do not match dialect {self.dialect.value}")
        for purpose, policy in self.model_policy.items():
            if policy.rows_in_prompt != "never" and purpose is not Purpose.NARRATE:
                raise ValueError(f"only 'narrate' may receive rows, not '{purpose.value}'")
        sql = self.model_policy.get(Purpose.SQL)
        if sql is not None and sql.temperature != 0.0:
            raise ValueError("the sql purpose must run at temperature 0")
        stray_roles = set(self.sql_visibility.roles) - set(self.roles)
        if stray_roles:
            raise ValueError(f"sql_visibility names unknown roles: {sorted(stray_roles)}")
        return self

    def content_sha256(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def ref(self) -> AppProfileRef:
        return AppProfileRef(
            id=self.id,
            version=self.version,
            dialect=self.dialect,
            content_sha256=self.content_sha256(),
        )


def load_app_profile(path: Path) -> AppProfile:
    """Load and validate apps/<app>/app.yaml. Stubs and invalid files are refused (fail closed)."""
    try:
        raw = load_yaml(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ProfileError(f"{path}: cannot read profile: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileError(f"{path}: profile must be a mapping")
    if raw.get("status") == "stub":
        raise ProfileError(f"{path}: profile is a stub (real inputs are missing); refusing to load")
    try:
        return AppProfile.model_validate(raw)
    except ValidationError as exc:
        raise ProfileError(f"{path}: invalid profile: {exc}") from exc
