"""The App Pack: everything app-specific the agents produce, as validated files.

The factory never branches on an app id; all domain knowledge lives here.
Layout of apppacks/<app_id>/:
    run.json            coordinator state (stages, gates, attempts)
    inputs/             the PRD text and a pointer to the supplied data
    manifest.yaml       personas, KPIs, signals, sources  (agent 1)
    data_contract.yaml  tables and fields every KPI needs  (agent 1)
    data/               CSVs as loaded (agent 2; versioned on recalibration)
    metrics.yaml        one verified SQL per KPI / signal figure (agent 3)
    insights/<app_id>/  governed AI profile for the insights layer (agent 3)
    ui.json             runtime UI configuration (agent 4)
    reports/            data, conformance and security reports (agents 2, 5)
    deploy/             Dockerfile, Bicep, deploy script (agent 5)
    handoffs/           one handoff.json per agent run
    logs/               one JSONL log per agent run
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from factory.config import APPPACKS_DIR

ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_id(value: str) -> str:
    if not ID_RE.match(value):
        raise ValueError(f"id {value!r} must be lower-case snake_case starting with a letter (max 41 chars)")
    return value


class IdModel(BaseModel):
    """Base for records with a snake_case `id`."""
    model_config = ConfigDict(extra="forbid")

    @field_validator("id", check_fields=False)
    @classmethod
    def _valid_id(cls, value: str) -> str:
        return _check_id(value)


# ---------------------------------------------------------------- manifest

class AppInfo(IdModel):
    id: str
    name: str
    domain: str
    description: str
    today: date | None = Field(None, description="Fixed 'today' the PRD figures assume, if any")
    phi: bool = Field(False, description="True if the app handles personal health or other sensitive personal data")


class Persona(IdModel):
    id: str
    name: str
    role: str
    focus: str = ""
    scope: dict[str, list[str]] = Field(default_factory=dict,
                                        description="Row-level scope, e.g. {'county': ['Humboldt']}")
    questions: list[str] = Field(default_factory=list, description="Suggested questions from the PRD")


Unit = Literal["count", "percent", "currency", "duration", "distance", "rate", "ratio", "text", "other"]


class Kpi(IdModel):
    id: str
    persona: str
    label: str
    value: str = Field(description="The figure exactly as the PRD shows it, e.g. '61%' or '$1.4M'")
    target: float | None = Field(None, description="Numeric form of value in the unit, e.g. 61 for 61%, 1400000 for $1.4M")
    unit: Unit = "count"
    prior: str | None = None
    definition: str
    sources: list[str] = Field(default_factory=list)


class SubFigure(Strict):
    name: str
    value: float
    unit: Unit = "count"
    description: str = ""

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        return _check_id(value)


class Signal(IdModel):
    id: str
    persona: str
    title: str
    severity: Literal["critical", "warning", "info"]
    description: str
    headline: float | None = None
    unit: Unit = "count"
    sub_figures: list[SubFigure] = Field(default_factory=list)


class DataSource(Strict):
    name: str
    records: str | None = None
    description: str = ""


class Manifest(Strict):
    app: AppInfo
    personas: list[Persona]
    kpis: list[Kpi] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    data_sources: list[DataSource] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _refs(self) -> "Manifest":
        persona_ids = {p.id for p in self.personas}
        for group in (self.kpis, self.signals):
            ids = [x.id for x in group]
            dupes = {i for i in ids if ids.count(i) > 1}
            if dupes:
                raise ValueError(f"duplicate ids: {sorted(dupes)}")
            for x in group:
                if x.persona not in persona_ids:
                    raise ValueError(f"{x.id}: unknown persona {x.persona!r}; known: {sorted(persona_ids)}")
        return self


# ----------------------------------------------------------- data contract

class ContractColumn(Strict):
    name: str
    type: Literal["text", "integer", "numeric", "boolean", "date", "timestamp"]
    description: str = ""


class ContractTable(Strict):
    name: str
    purpose: str
    key: str | None = None
    columns: list[ContractColumn]


class KpiCoverage(Strict):
    id: str = Field(description="KPI id or signal id (signal sub-figures as '<signal_id>.<name>')")
    tables: list[str]
    rationale: str


class DataContract(Strict):
    tables: list[ContractTable]
    coverage: list[KpiCoverage] = Field(default_factory=list)


# ------------------------------------------------------------------- metrics

class Metric(Strict):
    id: str = Field(description="KPI id, signal id (headline) or '<signal_id>.<sub_figure>'")
    sql: str
    value: float | str | None = None
    computed_at: str | None = None
    note: str = ""


class Metrics(Strict):
    metrics: list[Metric] = Field(default_factory=list)


# ---------------------------------------------------------------- app pack

class AppPack:
    def __init__(self, app_id: str):
        _check_id(app_id)
        self.app_id = app_id
        self.dir = APPPACKS_DIR / app_id
        for sub in ("inputs", "data", "reports", "deploy", "handoffs", "logs"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)

    # -- generic file helpers
    def path(self, *parts: str) -> Path:
        return self.dir.joinpath(*parts)

    def read_yaml(self, name: str, default=None):
        p = self.path(name)
        return yaml.safe_load(p.read_text(encoding="utf-8")) if p.is_file() else default

    def write_yaml(self, name: str, data) -> Path:
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return p

    def read_json(self, name: str, default=None):
        p = self.path(name)
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default

    def write_json(self, name: str, data) -> Path:
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return p

    # -- typed accessors
    def manifest(self) -> Manifest:
        raw = self.read_yaml("manifest.yaml")
        if raw is None:
            raise FileNotFoundError("manifest.yaml has not been written yet (agent 1)")
        return Manifest.model_validate(raw)

    def contract(self) -> DataContract:
        raw = self.read_yaml("data_contract.yaml")
        if raw is None:
            raise FileNotFoundError("data_contract.yaml has not been written yet (agent 1)")
        return DataContract.model_validate(raw)

    def metrics(self) -> Metrics:
        return Metrics.model_validate(self.read_yaml("metrics.yaml", {"metrics": []}))

    def save_metrics(self, metrics: Metrics) -> None:
        self.write_yaml("metrics.yaml", metrics.model_dump(mode="json"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
