"""Terminal demo of the agentic platform: every agent step, live, for both pipelines.

NLQ — one real question through the insights supervisor (live model, live governed Postgres):

    python -m insights.demo nlq "How many patients are currently enrolled?"
    python -m insights.demo nlq "What tables hold pregnancy episodes?" --persona maria

PRD — the data supervisor reading the product document and designing the platform:

    python -m insights.demo prd                   # REAL run (~10-20 min, real model tokens)
    python -m insights.demo prd --resume RUN_ID   # continue an interrupted run from checkpoint
    python -m insights.demo prd --replay          # instant replay of the last real run's
                                                  # recorded events (clearly marked, no model)

Every line is built from the run's own typed events — the same ones the chat UI and PRD Studio
render. The printer says per stage whether the skill is agentic (LLM loop), guarded
(deterministic core, bounded model use) or deterministic (no LLM), annotates where retrieval
came from (KAG vs entitlement-filtered catalog), shows fan-out branches, audit loop-backs, the
HITL pause, and per-stage duration + model tokens (tokens > 0 means the LLM was used).
"""

import argparse
import json
import logging
import sys
import threading
import time
from pathlib import Path

logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)
logging.getLogger("neo4j").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
PRD_OUT = ROOT / "artifacts" / "rain-prd-run"

NOTE_TEXT = {
    "kag_unavailable": "KAG unreachable -> retrieving from the entitlement-filtered CATALOG",
    "kag_error": "KAG errored -> retrieving from the entitlement-filtered CATALOG",
    "kag_low_coverage": "KAG covered too little -> retrieving from the entitlement-filtered CATALOG",
    "kag_hybrid": "KAG answered -> merged with the catalog retrieval (HYBRID path)",
    "metadata_bypass": "answered from the entitlement-filtered CATALOG (no SQL, no LLM)",
    "metadata_kag": "answered from the KNOWLEDGE GRAPH",
    "rows_held": "rows held BY REFERENCE in the result store (never enter agent state)",
    "sliver_tables": "entitled tables in the schema sliver",
    "synthesis_sources": "sources synthesized",
    "synthesis_failed_sources": "sources that FAILED (partial answer)",
    "policy_denied": "the L1 policy layer REFUSED the SQL",
    "dry_run_denied": "the L2 dry run REFUSED the SQL",
}

KIND_TEXT = {
    "agentic": "AGENTIC - bounded LLM loop",
    "guarded": "GUARDED - deterministic core",
    "deterministic": "DETERMINISTIC - no LLM",
}

REASON_TEXT = {
    "artifact_missing": "its artifact does not exist yet (next piece of the flow)",
    "intent_match": "it matches the routed intent",
    "refine_requested": "an agent sent work back for another pass",
    "refines_exhausted": "the refine budget is spent - moving on to the gates",
    "escalation": "a stage escalated - finishing honestly",
    "fanout_dispatch": "fanning out: one run per item",
    "pipeline_complete": "every stage is done - composing the final output",
    "max_steps": "the step budget was reached",
}

RULE = "-" * 74


def _say(text: str) -> None:
    print(text, flush=True)


class EventPrinter:
    """Pretty-prints typed StageEvents (as dicts) with the skill-kind legend from the registry."""

    def __init__(self, kinds: dict[str, str]):
        self.kinds = kinds

    def __call__(self, event) -> None:
        e = event if isinstance(event, dict) else event.model_dump(mode="json")
        kind = e.get("type")
        branch = f" [{e['branch']}]" if e.get("branch") else ""
        if kind == "graph_definition":
            _say("")
            _say(RULE)
            _say(f"  GRAPH   {e.get('agent_name')} v{e.get('agent_version')}"
                 + ("    *** DEMO REPLAY ***" if e.get("demo") else ""))
            steps = list(e.get("steps") or ())
            _say(f"  STAGES  {' -> '.join(steps[:5])}")
            if len(steps) > 5:
                _say(f"          -> {' -> '.join(steps[5:])}")
            _say("  the order below is DECIDED AT RUNTIME by the supervisor, not by this list")
            _say(RULE)
        elif kind == "supervisor_decision":
            why = REASON_TEXT.get(e.get("reason") or "", e.get("reason"))
            _say("")
            _say(f"[{e.get('count'):>2}] SUPERVISOR picks  {e.get('skill')}"
                 f"   (stage: {e.get('stage')})")
            _say(f"     because {why}")
        elif kind == "stage_started":
            legend = KIND_TEXT.get(self.kinds.get(e.get("skill") or "", ""), "")
            attempt = f"   pass {e.get('attempt') + 1}" if e.get("attempt") else ""
            _say(f"     >> START  {e.get('step_id')}{branch}   [{legend}]{attempt}")
        elif kind == "agent_iteration":
            _say(f"        . LLM loop iteration {e.get('iteration')}  (plan -> tool -> observe)")
        elif kind == "tool_call":
            _say(f"        . tool call: {e.get('tool')} -> {e.get('status')}")
        elif kind == "progress":
            note = e.get("note") or ""
            friendly = NOTE_TEXT.get(note)
            count = f" = {e.get('count')}" if e.get("count") is not None else ""
            _say(f"        . {note}{count}" + (f"\n          -> {friendly}" if friendly else ""))
        elif kind == "stage_finished":
            tokens = e.get("tokens") or {}
            total = (tokens.get("prompt_tokens") or 0) + (tokens.get("completion_tokens") or 0)
            llm = f"LLM: {total:,} tokens" if total else "no LLM"
            label = f"   result: {e.get('label')}" if e.get("label") else ""
            _say(f"     << DONE   {e.get('step_id')}{branch}   "
                 f"{(e.get('duration_ms') or 0) / 1000:.1f}s   {llm}{label}")
        elif kind == "refine":
            _say("")
            _say(f"     ~~ LOOP-BACK #{e.get('attempt')}  {e.get('step_id')} sent work back "
                 f"({e.get('label')}) - bounded by max_refines")
        elif kind == "hitl_waiting":
            _say("")
            _say(f"     ?? HUMAN REVIEW - run PAUSED ({e.get('reason')})")
            _say(f"        a reviewer decides: POST /api/v2/hitl/{e.get('run_id')}")
            _say("        no decision in time -> the answer is 'could not be verified'")
        elif kind == "hitl_decided":
            _say(f"     ?? HUMAN REVIEW resolved: {str(e.get('label', '')).upper()}")
        elif kind == "run_finished":
            tokens = e.get("tokens") or {}
            total = (tokens.get("prompt_tokens") or 0) + (tokens.get("completion_tokens") or 0)
            _say("")
            _say(RULE)
            _say(f"  RUN {str(e.get('outcome', '')).upper()}   "
                 f"{(e.get('duration_ms') or 0) / 1000:.1f}s   {total:,} gateway tokens"
                 + (f"   failure: {e.get('failure_reason')}" if e.get("failure_reason") else ""))
            _say(RULE)


def skill_kinds() -> dict[str, str]:
    from insights.skills_core.registry import SkillRegistry

    registry = SkillRegistry.scan(ROOT / "skills")
    return {name: registry.get(name).manifest.kind or "" for name in registry.names()}


# ---- NLQ ----------------------------------------------------------------------------------------


def run_nlq(args) -> int:
    from insights.api.auth import KeyRecord, entitlement_digest
    from insights.catalog.kag_neo4j import KagConfig, build_kag_provider
    from insights.catalog.provider import DirectoryCatalogs
    from insights.config import environment
    from insights.contracts.principal import Principal
    from insights.contracts.profile import load_app_profile
    from insights.datasources.provider import EnvDataSources
    from insights.gateway.config import GatewayConfig, build_gateway
    from insights.runtime.engine import Runtime
    from insights.runtime.hitl import HitlDecision, HitlStore
    from insights.runtime.stores import (
        InMemoryAuditSink,
        InMemoryResultStore,
        InMemoryRunStore,
    )
    from insights.runtime.supervisor import load_orchestrator
    from insights.skills_core.protocols import Services
    from insights.skills_core.registry import SkillRegistry

    env = environment(ROOT / "rain-api" / ".env")
    aliases = {
        "INSIGHTS_PG_HOST": "PG_HOST",
        "INSIGHTS_PG_PORT": "PG_PORT",
        "INSIGHTS_KAG_URI": "NEO4J_URI",
        "INSIGHTS_KAG_USER": "NEO4J_USER",
        "INSIGHTS_KAG_PASSWORD": "NEO4J_PASSWORD",
        "INSIGHTS_KAG_DATABASE": "NEO4J_DATABASE",
    }
    for target, source in aliases.items():
        if not env.get(target) and env.get(source):
            env[target] = env[source]

    app = load_app_profile(ROOT / "apps" / "rain" / "app.yaml")
    registry = SkillRegistry.scan(ROOT / "skills")
    orch = load_orchestrator(ROOT / "agents" / "insights" / "orchestrator.yaml")
    hitl = HitlStore()
    record = KeyRecord(id="demo", key_sha256="0" * 64, subject=args.persona, tenant="rain",
                       roles=(args.persona,))
    principal = Principal(subject=args.persona, tenant="rain", roles=(args.persona,),
                          entitlement_digest=entitlement_digest(record, app))
    runtime = Runtime(
        registry=registry,
        gateway=build_gateway(GatewayConfig.from_env(env)),
        audit=InMemoryAuditSink(),
        results=InMemoryResultStore(),
        runs=InMemoryRunStore(),
        services=Services(catalogs=DirectoryCatalogs(ROOT / "apps"),
                          kag=build_kag_provider(KagConfig.from_env(env)),
                          data=EnvDataSources(env), hitl=hitl),
    )

    def auto_approve() -> None:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            pending = hitl.pending()
            if pending:
                time.sleep(args.hitl_wait)
                hitl.decide(pending[0].run_id,
                            HitlDecision(action="approve", decided_by=f"{args.persona} (demo)"))
                _say(f"  ?? (demo reviewer approved after {args.hitl_wait:.0f}s)")
                return
            time.sleep(0.1)

    threading.Thread(target=auto_approve, daemon=True).start()
    _say(f"ASK ({args.persona}): {args.query}")
    record = runtime.run(
        orch, input={"query": args.query, "context": {}},
        principal=principal, app=app, on_event=EventPrinter(skill_kinds()),
    )
    answer = (record.output or {}).get("answer") or {}
    _say("\nANSWER")
    _say(f"  status:     {answer.get('status')}")
    if answer.get("reason"):
        _say(f"  reason:     {answer['reason'].get('code')} - {answer['reason'].get('message')}")
    if answer.get("row_count") is not None:
        _say(f"  rows:       {answer.get('row_count')}")
    refine = answer.get("refine") or {}
    if refine.get("path_used"):
        path = {"bypass": "catalog (bypass)", "kag": "knowledge graph (KAG)"}.get(
            refine["path_used"], refine["path_used"])
        _say(f"  retrieval:  {path}, after {refine.get('attempts', 0)} refine loop(s)")
    if answer.get("query") and answer["query"].get("sql"):
        _say(f"  sql:        {answer['query']['sql']}")
    if answer.get("narrative"):
        _say(f"  narrative:  {answer['narrative']}")
    confidence = answer.get("confidence") or {}
    if confidence:
        _say(f"  confidence: {confidence.get('score')}  signals: "
             f"{json.dumps(confidence.get('signals') or {})}")
    _say(f"  run_id:     {record.run_id}")
    return 0 if record.outcome == "completed" else 1


# ---- PRD ----------------------------------------------------------------------------------------


def prd_artifact_summary() -> None:
    import yaml

    _say("\nARTIFACTS the agents generated (artifacts/rain-prd-run/)")
    report_path = PRD_OUT / "run-report.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        usage = report.get("llm_usage") or {}
        _say(f"  run-report.json        completed={report.get('completed')}  "
             f"tokens={usage.get('total', 0):,} of {usage.get('run_token_budget', 0):,} budget")
        for stage, row in (report.get("stages") or {}).items():
            _say(f"    stage {stage:28} label={row.get('label')}  runs={row.get('runs')}")

    def _load(name: str):
        path = PRD_OUT / name
        if not path.is_file():
            return None
        if name.endswith(".json"):
            return json.loads(path.read_text(encoding="utf-8"))
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    ir = _load("requirements-ir.yaml")
    if ir:
        _say(f"  requirements-ir.yaml   {len(ir.get('personas') or [])} personas, "
             f"{len(ir.get('questions') or [])} extracted questions, "
             f"{len(ir.get('committed_figures') or [])} committed figures, "
             f"anchor_date={ir.get('anchor_date')}")
    registry = _load("question-registry.yaml")
    if registry:
        owners = {}
        for q in registry.get("questions") or []:
            owners[q.get("persona_id")] = owners.get(q.get("persona_id"), 0) + 1
        _say(f"  question-registry.yaml {len(registry.get('questions') or [])} questions "
             f"({', '.join(f'{k}={v}' for k, v in sorted(owners.items()))})")
    model = _load("entity-model.yaml")
    if model:
        _say(f"  entity-model.yaml      {len(model.get('tables') or [])} tables, "
             f"{len(model.get('relationships') or [])} relationships")
    lower = _load("lower-ontology.json")
    if lower:
        _say(f"  lower-ontology.json    {len(lower.get('nodes') or [])} nodes, "
             f"{len(lower.get('edges') or [])} edges (deterministic build from the model)")
    upper = _load("upper-ontology.json")
    if upper:
        kinds = {}
        for node in upper.get("nodes") or []:
            kinds[node.get("kind")] = kinds.get(node.get("kind"), 0) + 1
        _say(f"  upper-ontology.json    {len(upper.get('nodes') or [])} nodes "
             f"({', '.join(f'{k}={v}' for k, v in sorted(kinds.items()))}), "
             f"{len(upper.get('edges') or [])} edges")
    audit = _load("ontology-audit.json")
    if audit:
        _say(f"  ontology-audit.json    unmapped_concepts="
             f"{len(audit.get('unmapped_concepts') or [])}, invalid_edges="
             f"{len(audit.get('invalid_edge_references') or [])} (human-review flags)")
    scenario = _load("scenario.yaml")
    if scenario:
        _say(f"  scenario.yaml          {len(scenario.get('scenarios') or [])} SYNTHETIC "
             f"scenarios (never the live database)")


def run_prd(args) -> int:
    printer = EventPrinter(skill_kinds())

    if args.replay:
        events_path = PRD_OUT / "events.jsonl"
        if not events_path.is_file():
            _say("No recorded run to replay yet - run `python -m insights.demo prd` once first.")
            return 1
        _say("=" * 78)
        _say("DEMO REPLAY - recorded typed events of the LAST REAL RUN, time-compressed.")
        _say("Nothing is being generated; artifacts below are from that run.")
        _say("=" * 78)
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            event["demo"] = True
            printer(event)
            time.sleep(args.replay_delay)
        prd_artifact_summary()
        return 0

    from insights.config import environment
    from insights.prd.runner import PrdRunner

    env = environment(ROOT / "rain-api" / ".env" if (ROOT / "rain-api" / ".env").is_file()
                      else ROOT / ".env")
    _say(f"PRD TRIGGERED: {args.input}")
    _say("The data-pack supervisor reads the document and designs the platform from it.\n")
    runner = PrdRunner(env)
    report = runner.run(
        Path(args.input).resolve(),
        PRD_OUT,
        csv_dir=(ROOT / "rain-api" / "rain_source_csvs_prd").resolve(),
        catalog_path=(ROOT / "apps" / "rain" / "catalog" / "snapshot.json").resolve(),
        run_id=args.resume,
        resume=bool(args.resume),
        event_sink=printer,
    )
    prd_artifact_summary()
    if not report.get("completed"):
        _say(f"\nThe run did not complete; resume with: python -m insights.demo prd "
             f"--resume {report.get('run_id')}")
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    nlq = sub.add_parser("nlq", help="one real question through the insights supervisor")
    nlq.add_argument("query")
    nlq.add_argument("--persona", default="maria")
    nlq.add_argument("--hitl-wait", type=float, default=5.0,
                     help="seconds a HITL hold waits before the demo auto-approves")

    prd = sub.add_parser("prd", help="the PRD design pipeline through the data supervisor")
    prd.add_argument("--input", default=str(ROOT / "doc" / "RAIN_Prototype_Spec_v1.docx"))
    prd.add_argument("--resume", metavar="RUN_ID", help="continue from a checkpoint")
    prd.add_argument("--replay", action="store_true",
                     help="replay the last real run's recorded events instantly (no model)")
    prd.add_argument("--replay-delay", type=float, default=0.15)

    args = parser.parse_args(argv)
    return run_nlq(args) if args.command == "nlq" else run_prd(args)


if __name__ == "__main__":
    sys.exit(main())
