"""Golden-set eval: agentic skills vs the old single-shot baseline, on properties, not text.

5 PRD requirements-interpreter cases (tiny synthetic PRDs across domains) and 8 NLQ
query-generator cases run twice each: `agent` (the SkillAgent loop with tools, validators and
bounded repair) and `baseline` (one single-shot gateway call with the legacy prompt). Each case
is scored on expected PROPERTIES (persona recall, verbatim figures, the anchor-date rule,
grounded SQL), never exact text. Results land in artifacts/agentic-eval/report.json.

Run:  python -m insights.eval.agentic_golden            (full, real model)
      python -m insights.eval.agentic_golden --suite nlq
"""

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from insights.config import environment
from insights.contracts.enums import Purpose
from insights.contracts.gateway import Message
from insights.contracts.state import Sliver
from insights.gateway.base import GatewayError
from insights.prd.runner import ROOT, DesignRuntime
from insights.prd.tools import requirements_interpreter_agent
from insights.runtime.stores import InMemoryAuditSink, InMemoryResultStore, MonotonicDeadline, TokenMeter
from insights.skills_core.context import make_context
from insights.skills_core.protocols import Services

OUT_DIR = ROOT / "artifacts" / "agentic-eval"

LEGACY_IR_INSTRUCTION = """Return exactly one JSON object (JSON is valid YAML); no prose or markdown. Use this top-level shape: mode, domain, anchor_date, personas, questions, committed_figures, source_systems, entity_hints, narrative_events, constraints, open_items. Use empty arrays when a category has no evidence. Every persona needs id/name, role, altitude, problems, systems. Every extracted question needs id, persona_id, text, tier=extracted, is_data_question, and reason when false. Preserve stated figures exactly and record derivation/tolerance or an open item. Do not invent database tables or columns."""

PRD_CASES = [
    {
        "name": "clinic-relative-time",
        "document": (
            "Rural Clinic Ops Spec\n\nThis morning the triage queue spiked. Dr. Maria Delgado "
            "oversees 38 pregnant patients across the region. Nurse coordinator Sam Ortiz tracks "
            "1,204 transport requests a month and asks: How many transports ran today?\n"
        ),
        "personas": 2, "figures": ["38", "1,204"], "anchor_required": True,
    },
    {
        "name": "bank-ops",
        "document": (
            "Auto Loans Queue Spec\n\nQueue manager Priya Shah needs the service level, committed "
            "at 92% within two minutes. She asks: What is the current service level?\n"
        ),
        "personas": 1, "figures": ["92%"], "anchor_required": False,
    },
    {
        "name": "telecom-noc",
        "document": (
            "NOC Visibility Spec\n\nShift lead Omar watches tower outages. Capacity planner Lena "
            "models backhaul. Field tech Ravi closes tickets; 4,512 tickets were closed last "
            "quarter. Omar asks: Which towers are degraded right now?\n"
        ),
        "personas": 3, "figures": ["4,512"], "anchor_required": True,
    },
    {
        "name": "logistics-persona-only",
        "document": (
            "Fleet Health Spec\n\nDispatcher Ana struggles with stale vehicle telemetry. Mechanic "
            "lead Bruno cannot see fault histories. No example questions are listed yet.\n"
        ),
        "personas": 2, "figures": [], "anchor_required": False,
    },
    {
        "name": "retail-representative-persona",
        "document": (
            "Storefront Insights Spec\n\nMerchandiser Dana plans displays. The spec also designs "
            "for a representative Shopper persona (unnamed) using the mobile storefront. Dana "
            "asks: Which displays drove the 4,512 add-to-cart events last week?\n"
        ),
        "personas": 2, "figures": ["4,512"], "anchor_required": True,
    },
]

NLQ_SLIVER = {
    "tables": [
        {"source_id": "main", "name": "Patient", "columns": [
            {"name": "patient_id", "type": "text"}, {"name": "county", "type": "text"}]},
        {"source_id": "main", "name": "PregnancyEpisode", "columns": [
            {"name": "episode_id", "type": "text"}, {"name": "patient_id", "type": "text"},
            {"name": "risk_level", "type": "text"}, {"name": "start_date", "type": "date"}]},
        {"source_id": "main", "name": "TransportRequest", "columns": [
            {"name": "request_id", "type": "text"}, {"name": "patient_id", "type": "text"},
            {"name": "status", "type": "text"}, {"name": "requested_at", "type": "timestamp"}]},
    ],
    "joins": [
        {"left": "PregnancyEpisode.patient_id", "right": "Patient.patient_id"},
        {"left": "TransportRequest.patient_id", "right": "Patient.patient_id"},
    ],
    "glossary_terms": [], "coverage": 1.0, "path_used": "bypass", "catalog_version": "0" * 64,
}

NLQ_CASES = [
    {"name": "count-per-county", "query": "How many patients per county?",
     "expect_label": "generated", "must_use": ["patient"]},
    {"name": "elevated-risk", "query": "How many elevated-risk pregnancies are active?",
     "expect_label": "generated", "must_use": ["pregnancyepisode"]},
    {"name": "transports-by-status", "query": "Show transport requests by status",
     "expect_label": "generated", "must_use": ["transportrequest"]},
    {"name": "join-needed", "query": "Elevated-risk pregnancies by county",
     "expect_label": "generated", "must_use": ["pregnancyepisode", "patient"]},
    {"name": "top-counties", "query": "Top 3 counties by transport requests",
     "expect_label": "generated", "must_use": ["transportrequest"]},
    {"name": "monthly-trend", "query": "Transport requests per month this year",
     "expect_label": "generated", "must_use": ["transportrequest"]},
    {"name": "simple-count", "query": "How many patients are there?",
     "expect_label": "generated", "must_use": ["patient"]},
    {"name": "ungroundable", "query": "What is the average claim amount by payer?",
     "expect_label": None, "must_use": []},  # no claims table: generated-but-grounded or unusable
]


def _normalized(text: str) -> str:
    return re.sub(r"[,\s]", "", str(text))


def score_prd(case: dict[str, Any], ir: Any) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    ok = isinstance(ir, dict)
    checks["valid_object"] = ok
    personas = (ir.get("personas") if ok else None) or []
    personas = list(personas.values()) if isinstance(personas, dict) else personas
    checks["persona_recall"] = len(personas) == case["personas"]
    values = {
        _normalized(f.get("value"))
        for f in ((ir.get("committed_figures") if ok else None) or [])
        if isinstance(f, dict) and f.get("value") is not None
    }
    checks["figures_verbatim"] = all(_normalized(v) in values for v in case["figures"])
    checks["anchor_rule"] = (not case["anchor_required"]) or bool(ok and ir.get("anchor_date"))
    ids = {str(p.get("id") or p.get("persona_id")) for p in personas if isinstance(p, dict)}
    questions = (ir.get("questions") if ok else None) or []
    checks["questions_owned"] = all(
        str(q.get("persona_id")) in ids for q in questions if isinstance(q, dict)
    )
    return checks


def score_nlq(case: dict[str, Any], out: dict[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    if case["expect_label"]:
        checks["label"] = out.get("label") == case["expect_label"]
    used = {str(t).lower() for t in out.get("tables_used") or []}
    allowed = {t["name"].lower() for t in NLQ_SLIVER["tables"]}
    checks["grounded"] = out.get("label") != "generated" or used <= allowed
    checks["must_use"] = all(t in used for t in case["must_use"]) if out.get("label") == "generated" else not case["must_use"]
    return checks


class _Catalogs:
    def for_app(self, app):
        from types import SimpleNamespace

        return SimpleNamespace(catalog=SimpleNamespace(
            examples=(), vocabulary=frozenset(), glossary=SimpleNamespace(terms=[])
        ))


def _ctx(design: DesignRuntime, step_id: str, timeout_ms: int) -> dict[str, Any]:
    import uuid

    return make_context(
        run_id=uuid.uuid4().hex, trace_id=uuid.uuid4().hex, step_id=step_id, attempt=0,
        principal=design.principal, app=design.app, gateway=design.gateway,
        emit=lambda note, count=None: None, audit=InMemoryAuditSink(),
        results=InMemoryResultStore(), usage=TokenMeter(),
        deadline=MonotonicDeadline(time.monotonic, timeout_ms), services=Services(catalogs=_Catalogs()),
    )


def run_prd_case(design: DesignRuntime, case: dict[str, Any], mode: str) -> dict[str, Any]:
    started = time.monotonic()
    if mode == "agent":
        agent = requirements_interpreter_agent()
        ctx = _ctx(design, "requirements_interpreter", agent.spec.timeout_ms)
        out = agent.run({"document": case["document"], "document_name": f"{case['name']}.md"}, ctx)
        ir = out.get("requirements_ir")
        meta = {"iterations": out["iterations"], "tool_calls": out["tool_calls"],
                "repairs": out["repairs"], "tokens": ctx["usage"].total().total,
                "label": out["label"]}
    else:
        from insights.prd.schemas import artifact_schema
        from insights.prd.tools import _prompt_body

        ctx = _ctx(design, "requirements_interpreter", 900_000)
        system = _prompt_body(ROOT / "skills" / "requirements-interpreter" / "SKILL.md") + "\n\n" + LEGACY_IR_INSTRUCTION
        try:
            result = ctx["gateway"].complete(
                [Message(role="system", content=system),
                 Message(role="user", content=case["document"])],
                Purpose.DESIGN, ctx, response_schema=artifact_schema("requirements-interpreter"),
            )
            ir = result.content if isinstance(result.content, dict) else None
        except GatewayError as exc:
            ir = None
        meta = {"iterations": 1, "tool_calls": 0, "repairs": 0,
                "tokens": ctx["usage"].total().total, "label": "single_shot"}
    checks = score_prd(case, ir)
    return {"case": case["name"], "mode": mode, "wall_s": round(time.monotonic() - started, 1),
            **meta, "checks": checks, "score": round(sum(checks.values()) / len(checks), 3)}


def run_nlq_case(design: DesignRuntime, registry, case: dict[str, Any], mode: str) -> dict[str, Any]:
    from insights.skills_core.registry import SkillRegistry

    started = time.monotonic()
    ctx = _ctx(design, "generate", 120_000)
    if mode == "agent":
        skill = registry.get("query-generator")
        out = skill.run({"query": case["query"], "sliver": NLQ_SLIVER}, ctx)
        meta = {"repairs": out.get("repairs", 0)}
    else:
        # the pre-agent baseline: one call, no tools, no repair; grounded check applied after
        from insights.catalog.examples import tables_read_by

        system = (
            "Write ONE PostgreSQL SELECT answering the question using ONLY these tables/columns:\n"
            + json.dumps({t["name"]: [c["name"] for c in t["columns"]] for t in NLQ_SLIVER["tables"]})
            + '\nAnswer as JSON: {"sql": "...", "assumptions": [], "tables_used": []}'
        )
        try:
            result = ctx["gateway"].complete(
                [Message(role="system", content=system),
                 Message(role="user", content=case["query"])],
                Purpose.SQL, ctx,
                response_schema={"type": "object", "required": ["sql"],
                                 "properties": {"sql": {"type": "string"},
                                                "assumptions": {"type": "array"},
                                                "tables_used": {"type": "array"}},
                                 "additionalProperties": True},
            )
            sql = str(result.content.get("sql") or "")
            try:
                used = tables_read_by(sql, "postgres")
            except ValueError:
                used = []
            allowed = {t["name"].lower() for t in NLQ_SLIVER["tables"]}
            grounded = bool(used) and set(used) <= allowed
            out = {"label": "generated" if grounded else "unusable", "sql": sql, "tables_used": used}
        except GatewayError:
            out = {"label": "unusable", "tables_used": []}
        meta = {"repairs": 0}
    checks = score_nlq(case, out)
    return {"case": case["name"], "mode": mode, "wall_s": round(time.monotonic() - started, 1),
            "tokens": ctx["usage"].total().total, "label": out.get("label"), **meta,
            "checks": checks, "score": round(sum(checks.values()) / len(checks), 3)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["prd", "nlq", "all"], default="all")
    args = parser.parse_args(argv)
    env_path = ROOT / ".env"
    if not env_path.is_file():
        env_path = ROOT / "rain-api" / ".env"
    design = DesignRuntime(environment(env_path))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    if args.suite in ("prd", "all"):
        for case in PRD_CASES:
            for mode in ("baseline", "agent"):
                row = run_prd_case(design, case, mode)
                results.append(row)
                print(json.dumps(row), flush=True)
    if args.suite in ("nlq", "all"):
        from insights.skills_core.registry import SkillRegistry

        registry = SkillRegistry.scan(ROOT / "skills")
        for case in NLQ_CASES:
            for mode in ("baseline", "agent"):
                row = run_nlq_case(design, registry, case, mode)
                results.append(row)
                print(json.dumps(row), flush=True)

    def mean(rows, key):
        rows = list(rows)
        return round(sum(r[key] for r in rows) / len(rows), 3) if rows else None

    summary = {}
    for suite in ("prd", "nlq"):
        for mode in ("baseline", "agent"):
            rows = [r for r in results
                    if r["mode"] == mode and (r["case"] in {c["name"] for c in (PRD_CASES if suite == "prd" else NLQ_CASES)})]
            if rows:
                summary[f"{suite}:{mode}"] = {
                    "cases": len(rows), "mean_score": mean(rows, "score"),
                    "mean_tokens": mean(rows, "tokens"), "mean_wall_s": mean(rows, "wall_s"),
                }
    report = {"summary": summary, "results": results}
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("SUMMARY " + json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
