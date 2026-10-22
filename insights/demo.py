"""Terminal walkthrough of one NLQ through the insights supervisor: every agent step, live.

    python -m insights.demo "How many patients are currently enrolled?"
    python -m insights.demo "What tables hold pregnancy episodes?" --persona maria

Runs the REAL pipeline (live gateway, live governed Postgres) and prints each typed event the
engine emits — the same events the chat UI renders: which agent the supervisor picked and why,
every stage start/finish with duration and tokens, agent-loop iterations and tool calls, fan-out
branches, loop-backs, and the HITL hold (auto-approved after --hitl-wait seconds so the demo
never hangs; in the product a human decides via POST /api/v2/hitl/<run_id>).
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
from insights.runtime.stores import InMemoryAuditSink, InMemoryResultStore, InMemoryRunStore
from insights.runtime.supervisor import load_orchestrator
from insights.skills_core.protocols import Services
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[1]


def _say(text: str) -> None:
    print(text, flush=True)


def print_event(event) -> None:
    kind = event.type.value
    branch = f" [{event.branch}]" if event.branch else ""
    if kind == "graph_definition":
        _say(f"\nGRAPH  {event.agent_name} v{event.agent_version}")
        _say(f"       stages: {' -> '.join(event.steps)}")
        _say("       (the ORDER below is decided at runtime by the supervisor, not this list)\n")
    elif kind == "supervisor_decision":
        considered = ", ".join(event.considered or ())
        _say(f"SUPERVISOR  decision #{event.count}: run '{event.skill}' for stage "
             f"'{event.stage}'")
        _say(f"            why: {event.reason}   considered: {considered}")
    elif kind == "stage_started":
        _say(f"  >> {event.step_id}{branch}  ({event.skill} v{event.skill_version}, "
             f"attempt {event.attempt})")
    elif kind == "agent_iteration":
        _say(f"     .. agent loop iteration {event.iteration}")
    elif kind == "tool_call":
        _say(f"     .. tool {event.tool} -> {event.status}")
    elif kind == "progress":
        count = f"={event.count}" if event.count is not None else ""
        _say(f"     .. {event.note}{count}")
    elif kind == "stage_finished":
        tokens = event.tokens.total if event.tokens else 0
        _say(f"  << {event.step_id}{branch}  label={event.label}  "
             f"{event.duration_ms} ms  {tokens} tokens")
    elif kind == "refine":
        _say(f"  ~~ LOOP-BACK #{event.attempt}: {event.step_id} asked for {event.label}")
    elif kind == "hitl_waiting":
        _say(f"  ?? HUMAN REVIEW: the run is PAUSED ({event.reason}). A reviewer decides via "
             f"POST /api/v2/hitl/{event.run_id} — timeout answers 'could not be verified'.")
    elif kind == "hitl_decided":
        _say(f"  ?? HUMAN REVIEW resolved: {event.label}")
    elif kind == "run_finished":
        tokens = event.tokens.total if event.tokens else 0
        _say(f"\nRUN {event.outcome.upper()} in {event.duration_ms} ms, {tokens} gateway tokens")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="the natural-language question")
    parser.add_argument("--persona", default="maria", help="rain persona role (default maria)")
    parser.add_argument("--hitl-wait", type=float, default=5.0,
                        help="seconds a HITL hold waits before the demo auto-approves")
    args = parser.parse_args(argv)

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
        principal=principal, app=app, on_event=print_event,
    )
    answer = (record.output or {}).get("answer") or {}
    _say("\nANSWER")
    _say(f"  status:     {answer.get('status')}")
    if answer.get("reason"):
        _say(f"  reason:     {answer['reason'].get('code')} — {answer['reason'].get('message')}")
    if answer.get("row_count") is not None:
        _say(f"  rows:       {answer.get('row_count')}")
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


if __name__ == "__main__":
    sys.exit(main())
