"""Agent 1 (Requirements) tools: PRD -> App Manifest + data contract.

The manifest is built in parts (app, personas, KPIs, signals, sources) into a
draft, so a large PRD never has to fit in one tool call; every save validates."""
from __future__ import annotations

from pydantic import ValidationError

from factory.apppack import (AppInfo, ContractTable, DataContract, DataSource, Kpi, KpiCoverage, Manifest,
                             Persona, Signal)
from factory.tools import RunContext, tool

DRAFT = "manifest.draft.json"
CONTRACT_DRAFT = "data_contract.draft.json"


def _draft(ctx: RunContext) -> dict:
    return ctx.pack.read_json(DRAFT, {"app": None, "personas": [], "kpis": [], "signals": [],
                                      "data_sources": [], "notes": []})


def _upsert(items: list[dict], new: list[dict], key: str = "id") -> list[dict]:
    by_id = {i[key]: i for i in items}
    for n in new:
        by_id[n[key]] = n
    return list(by_id.values())


def _errors(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()][:30]


@tool("read_prd", "Return the full text of the PRD (tables are rendered as ' | '-separated rows).", {})
def read_prd(ctx: RunContext):
    return ctx.pack.path("inputs", "prd.txt").read_text(encoding="utf-8")


@tool("save_app_info", "Save the app identity. `id` must equal the run's app id.",
      {"app": {"type": "object", "description": "AppInfo: id, name, domain, description, today (YYYY-MM-DD or null), phi"}},
      ["app"])
def save_app_info(ctx: RunContext, app: dict):
    if app.get("id") != ctx.pack.app_id:
        return {"error": f"app.id must be {ctx.pack.app_id!r}"}
    try:
        AppInfo.model_validate(app)
    except ValidationError as exc:
        return {"error": _errors(exc)}
    d = _draft(ctx)
    d["app"] = app
    ctx.pack.write_json(DRAFT, d)
    return {"saved": "app"}


@tool("save_personas",
      "Add or replace personas (by id). Fields: id (snake_case), name, role, focus, scope "
      "(row-level scope such as {\"county\": [\"Humboldt\"]} if the PRD limits what this persona covers), "
      "questions (the persona's suggested questions from the PRD, verbatim).",
      {"personas": {"type": "array", "items": {"type": "object"}}}, ["personas"])
def save_personas(ctx: RunContext, personas: list[dict]):
    try:
        for p in personas:
            Persona.model_validate(p)
    except ValidationError as exc:
        return {"error": _errors(exc)}
    d = _draft(ctx)
    d["personas"] = _upsert(d["personas"], personas)
    ctx.pack.write_json(DRAFT, d)
    return {"personas": [p["id"] for p in d["personas"]]}


@tool("save_kpis",
      "Add or replace KPIs (by id). One entry per dashboard KPI in the PRD. Fields: id, persona, label, "
      "value (exactly as printed), target (number in the unit: 61 for '61%', 1400000 for '$1.4M', "
      "10200 for '10,200 sq mi'), unit (count|percent|currency|duration|distance|rate|ratio|text|other), "
      "prior (e.g. 'was 84%'), definition (what is counted, in plain words, using the PRD's own wording), "
      "sources (PRD source systems).",
      {"kpis": {"type": "array", "items": {"type": "object"}}}, ["kpis"])
def save_kpis(ctx: RunContext, kpis: list[dict]):
    try:
        for k in kpis:
            Kpi.model_validate(k)
    except ValidationError as exc:
        return {"error": _errors(exc)}
    d = _draft(ctx)
    d["kpis"] = _upsert(d["kpis"], kpis)
    ctx.pack.write_json(DRAFT, d)
    return {"kpi_count": len(d["kpis"])}


@tool("save_signals",
      "Add or replace priority signals (by id). Fields: id, persona, title, severity "
      "(critical|warning|info), description (the PRD text), headline (the main number), unit, "
      "sub_figures: every other number the signal text states, each {name (snake_case), value, unit, description}.",
      {"signals": {"type": "array", "items": {"type": "object"}}}, ["signals"])
def save_signals(ctx: RunContext, signals: list[dict]):
    try:
        for s in signals:
            Signal.model_validate(s)
    except ValidationError as exc:
        return {"error": _errors(exc)}
    d = _draft(ctx)
    d["signals"] = _upsert(d["signals"], signals)
    ctx.pack.write_json(DRAFT, d)
    return {"signal_count": len(d["signals"])}


@tool("save_data_sources", "Save the PRD's list of source systems (name, records as printed, description).",
      {"data_sources": {"type": "array", "items": {"type": "object"}},
       "notes": {"type": "array", "items": {"type": "string"},
                 "description": "Ambiguities or conflicts you found in the PRD"}},
      ["data_sources"])
def save_data_sources(ctx: RunContext, data_sources: list[dict], notes=None):
    try:
        for s in data_sources:
            DataSource.model_validate(s)
    except ValidationError as exc:
        return {"error": _errors(exc)}
    d = _draft(ctx)
    d["data_sources"] = data_sources
    d["notes"] = notes or d.get("notes", [])
    ctx.pack.write_json(DRAFT, d)
    return {"source_count": len(data_sources)}


@tool("validate_manifest",
      "Validate the draft and, if valid, write manifest.yaml. Returns counts or the list of errors to fix.", {})
def validate_manifest(ctx: RunContext):
    d = _draft(ctx)
    if not d.get("app"):
        return {"error": "save_app_info first"}
    try:
        m = Manifest.model_validate(d)
    except ValidationError as exc:
        return {"error": _errors(exc)}
    ctx.pack.write_yaml("manifest.yaml", m.model_dump(mode="json"))
    numeric = sum(1 for k in m.kpis if k.target is not None)
    subs = sum(len(s.sub_figures) for s in m.signals)
    return {"written": "manifest.yaml", "personas": len(m.personas), "kpis": len(m.kpis),
            "kpis_with_numeric_target": numeric, "signals": len(m.signals), "signal_sub_figures": subs}


@tool("save_data_contract",
      "Add or replace data-contract tables (by name) and KPI coverage. Tables: name (snake_case), purpose, "
      "key, columns [{name, type: text|integer|numeric|boolean|date|timestamp, description}]. Coverage: "
      "{id: kpi id, signal id, or '<signal_id>.<sub_figure>', tables, rationale}.",
      {"tables": {"type": "array", "items": {"type": "object"}},
       "coverage": {"type": "array", "items": {"type": "object"}}},
      [])
def save_data_contract(ctx: RunContext, tables=None, coverage=None):
    draft = ctx.pack.read_json(CONTRACT_DRAFT, {"tables": [], "coverage": []})
    try:
        for t in tables or []:
            ContractTable.model_validate(t)
        for c in coverage or []:
            KpiCoverage.model_validate(c)
    except ValidationError as exc:
        return {"error": _errors(exc)}
    draft["tables"] = _upsert(draft["tables"], tables or [], key="name")
    draft["coverage"] = _upsert(draft["coverage"], coverage or [])
    contract = DataContract.model_validate(draft)
    ctx.pack.write_json(CONTRACT_DRAFT, draft)
    ctx.pack.write_yaml("data_contract.yaml", contract.model_dump(mode="json"))
    uncovered = []
    if ctx.pack.path("manifest.yaml").is_file():
        m = ctx.pack.manifest()
        covered = {c.id for c in contract.coverage}
        wanted = [k.id for k in m.kpis if k.target is not None] + [s.id for s in m.signals if s.headline is not None]
        uncovered = [w for w in wanted if w not in covered]
    return {"tables": len(contract.tables), "coverage": len(contract.coverage), "not_yet_covered": uncovered}
