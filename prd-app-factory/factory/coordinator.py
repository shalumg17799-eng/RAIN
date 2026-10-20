"""Coordinator: a deterministic workflow (not a model) that runs the five agents
in order, stops at the three human gates, and routes conformance failures back
to the data agent (cause "data") or the knowledge agent (cause "metric").

    requirements -> gate A -> data -> gate B -> knowledge -> app -> verify
                                   ^-------- loop (max 2) -------'   |
                                                                   gate C -> release
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.agents import AGENTS
from factory.apppack import AppPack, now
from factory.prd_text import extract
from factory.runtime import run_agent
from factory.tools import RunContext

ORDER = ["requirements", "gate:A", "data", "gate:B", "knowledge", "app", "verify", "gate:C", "release", "done"]
GATES = {
    "A": "Review manifest.yaml and data_contract.yaml: personas, every KPI and signal figure, definitions.",
    "B": "Review reports/data_versions.json, reports/dq.json and the data agent's handoff: what was loaded or generated.",
    "C": "Review reports/conformance.md, reports/security.json, reports/smoke.json and reports/findings.json.",
}


def _state(pack: AppPack) -> dict:
    s = pack.read_json("run.json")
    if s is None:
        raise SystemExit(f"no run for app {pack.app_id!r}; start one with `python -m factory run`")
    return s


def _save(pack: AppPack, s: dict) -> None:
    s["updated_at"] = now()
    pack.write_json("run.json", s)


def start(app_id: str, prd: str, data: str | None, target: float, max_loops: int,
          auto_gates: list[str] | None = None) -> AppPack:
    pack = AppPack(app_id)
    if pack.read_json("run.json"):
        raise SystemExit(f"apppacks/{app_id} already has a run; use `resume`, or pick a new app id")
    pack.path("inputs", "prd.txt").write_text(extract(prd), encoding="utf-8")
    pack.write_json("inputs/data_source.json", {"path": str(Path(data).resolve()) if data else None,
                                                 "prd": str(Path(prd).resolve())})
    _save(pack, {"app_id": app_id, "created_at": now(), "stage": "requirements", "status": "running",
                 "target": target, "max_loops": max_loops, "loops": 0, "gates": {}, "feedback": {},
                 "auto_gates": [g for g in (auto_gates or []) if g in ("A", "B")],
                 "history": [], "usage": {}})
    return pack


def approve(app_id: str, gate: str, by: str, note: str = "") -> None:
    pack = AppPack(app_id)
    s = _state(pack)
    s["gates"][gate] = {"status": "approved", "by": by, "note": note, "at": now()}
    if s["stage"] == f"gate:{gate}":
        s["status"] = "running"
    _save(pack, s)


def retry(app_id: str, by: str, note: str = "") -> None:
    """Clear a blocked stage (after a person fixed its cause) so the next advance runs it again."""
    pack = AppPack(app_id)
    s = _state(pack)
    if not s["status"].startswith("blocked"):
        raise ValueError(f"run is not blocked (status: {s['status']})")
    s["history"].append({"at": now(), "event": "retry", "stage": s["stage"], "by": by, "note": note})
    s["status"] = "running"
    _save(pack, s)


def _task(pack: AppPack, stage: str, s: dict) -> str:
    app = pack.app_id
    base = f"App id: {app}. App Pack folder: apppacks/{app}. "
    if stage == "requirements":
        return base + "Read the PRD and write the App Manifest (manifest.yaml) and the data contract (data_contract.yaml)."
    if stage == "data":
        fb = s["feedback"].get("data")
        if fb:
            return base + ("RECALIBRATION. Agent 5 found PRD figures the loaded data cannot reproduce. Fix the data "
                           "with minimal changes (see your skill), load a new version and re-run affected DQ checks. "
                           f"Findings:\n{json.dumps(fb, indent=1)}")
        src = pack.read_json("inputs/data_source.json", {}).get("path")
        return base + (f"Supplied data folder: {src}. " if src else "No data was supplied: generate it. ") + \
            "Profile, load into the staging schema as the first data version, check against the data contract, " \
            "record data-quality checks."
    if stage == "knowledge":
        fb = s["feedback"].get("metric")
        extra = ""
        if fb:
            extra = f"\nAgent 5 says these metric definitions are wrong; fix them:\n{json.dumps(fb, indent=1)}"
        if s["loops"]:
            extra += ("\nThe data may have been recalibrated since your last run: re-check every figure with "
                      "`list_figures` and re-save any metric whose definition must change. Keep the governed "
                      "profile, ontology and examples unless the schema changed.")
        return base + ("Build the metric layer for every PRD figure, then the join hints, ontology, examples and "
                       "the governed AI profile." if not s["loops"] else "Update the metric layer.") + extra
    if stage == "app":
        return base + "Configure ui.json for every persona and preview the runtime."
    if stage == "verify":
        return base + "MODE: verify. Run the conformance verdict, diagnose and classify every figure that is not a " \
                      "live match, run the security checks and the smoke test, and record findings."
    if stage == "release":
        return base + "MODE: release. Gate C is approved. Prepare the deployment kit, deploy to Azure if access " \
                      "exists, and write the release notes."
    raise ValueError(stage)


def _route_after_verify(pack: AppPack, s: dict) -> str:
    report = pack.read_json("reports/conformance.json", {})
    findings = pack.read_json("reports/findings.json", {}).get("findings", [])
    rate = report.get("rate_with_static", 0)
    data = [f for f in findings if f["cause"] == "data"]
    metric = [f for f in findings if f["cause"] == "metric"]
    s["history"].append({"at": now(), "event": "verdict", "rate_live": report.get("rate"), "rate_with_static": rate,
                         "data_findings": len(data), "metric_findings": len(metric)})
    if rate >= s["target"] or s["loops"] >= s["max_loops"] or not (data or metric):
        s["feedback"] = {}
        return "gate:C"
    s["loops"] += 1
    s["feedback"] = {"data": data, "metric": metric}
    return "data" if data else "knowledge"


STAGE_AGENT = {"requirements": "requirements", "data": "data", "knowledge": "knowledge", "app": "app",
               "verify": "release", "release": "release"}


def run_stage(app_id: str, stage: str) -> dict:
    """Run one agent stage, record its handoff and move the run to the next stage."""
    pack = AppPack(app_id)
    s = _state(pack)
    if s["stage"] != stage:
        return {"skipped": f"run is at {s['stage']!r}, not {stage!r}"}   # duplicate or stale message
    agent = STAGE_AGENT[stage]
    ctx = RunContext(pack=pack, agent=agent, mode=stage if agent == "release" else "",
                     approved_gates={g for g, v in s["gates"].items() if v.get("status") == "approved"})
    s["status"] = f"running {stage}"
    _save(pack, s)
    try:
        handoff = run_agent(AGENTS[agent], ctx, _task(pack, stage, s))
    except Exception as exc:  # an agent crash blocks the run with the reason, it never loses state
        handoff = {"status": "blocked", "summary": f"agent error: {type(exc).__name__}: {str(exc)[:500]}"}
    s = _state(pack)
    u = handoff.get("usage", {})
    for k, v in u.items():
        s["usage"][k] = s["usage"].get(k, 0) + v
    s["history"].append({"at": now(), "stage": stage, "status": handoff["status"],
                         "summary": handoff.get("summary", "")[:2000], "usage": u})
    if handoff["status"] != "ok":
        s["status"] = f"blocked at {stage}"
        _save(pack, s)
        print(f"\n>>> Blocked at {stage}: {handoff.get('summary')}")
        return handoff
    if stage == "data" and s["feedback"].get("data"):
        s["feedback"].pop("data")
        nxt = "knowledge"
    elif stage == "knowledge" and s["loops"]:
        s["feedback"].pop("metric", None)
        nxt = "verify"
    elif stage == "verify":
        nxt = _route_after_verify(pack, s)
    else:
        nxt = ORDER[ORDER.index(stage) + 1]
    s["stage"], s["status"] = nxt, "running"
    _save(pack, s)
    return handoff


def advance(app_id: str, auto_approve: bool = False, dispatch=None) -> dict:
    """Move the run forward until it is done, blocked, waiting at a gate or - with `dispatch` -
    handed to an agent's queue. `dispatch(app_id, stage)` is how the portal and the queue workers
    run stages on separate agent jobs; without it every stage runs in this process."""
    pack = AppPack(app_id)
    s = _state(pack)
    while s["stage"] != "done":
        stage = s["stage"]
        if s["status"].startswith("blocked"):
            return s
        if stage.startswith("gate:"):
            gate = stage.split(":")[1]
            if s["gates"].get(gate, {}).get("status") != "approved":
                if not (auto_approve or gate in s.get("auto_gates", [])):
                    s["status"] = f"waiting for gate {gate}"
                    _save(pack, s)
                    print(f"\n>>> Waiting at gate {gate}: {GATES[gate]}\n    Approve with: python -m factory "
                          f"approve --app {app_id} --gate {gate}   then: python -m factory resume --app {app_id}")
                    return s
                s["gates"][gate] = {"status": "approved", "by": "auto (configured for this run)", "at": now()}
            s["stage"], s["status"] = ORDER[ORDER.index(stage) + 1], "running"
            _save(pack, s)
            continue
        if dispatch is not None:
            s["status"] = f"queued {stage}"
            _save(pack, s)
            dispatch(app_id, stage)
            return s
        run_stage(app_id, stage)
        s = _state(pack)
    s["status"] = "done"
    _save(pack, s)
    return s
