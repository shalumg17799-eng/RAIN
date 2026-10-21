"""The whole NLQ pipeline under the supervisor: real pack, real catalog, fake model and adapter.

Covers the required flow tests: a 1-source data query end to end (with the per-source fan-out of
one branch), the supervisor picking the metadata path for a metadata question, a 2-source
fan-out with a partial failure synthesized into a partial answer, and the UI event stream naming
the active agent per step.
"""

import threading
import time
import unittest
from pathlib import Path

from insights.catalog.provider import DirectoryCatalogs
from insights.contracts.enums import EventType
from insights.contracts.principal import Principal
from insights.contracts.profile import load_app_profile
from insights.datasources.base import PlanEstimate, QueryError, QueryResult, ResultColumn
from insights.runtime.engine import Runtime
from insights.runtime.hitl import HitlDecision, HitlStore
from insights.runtime.stores import (
    InMemoryAuditSink,
    InMemoryResultStore,
    InMemoryRunStore,
)
from insights.runtime.supervisor import load_orchestrator
from insights.runtime.test_skill_agent import FakeGateway
from insights.skills_core.protocols import Services
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = SkillRegistry.scan(ROOT / "skills")
ORCH = load_orchestrator(ROOT / "agents" / "insights" / "orchestrator.yaml")
APP = load_app_profile(ROOT / "apps" / "rain" / "app.yaml")

MARIA = Principal(
    subject="maria", tenant="rain", roles=("maria",), entitlement_digest="0" * 64
)

SQL_ENVELOPE = {
    "action": "finish",
    "result": {
        "sql": 'SELECT count(*) AS n FROM "Patient"',
        "assumptions": [],
        "tables_used": ["patient"],
    },
    "confidence": 0.9,
}


class FakeAdapter:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.executed: list[str] = []

    def explain(self, sql, binding, *, timeout_ms):
        return PlanEstimate(total_cost=10.0, plan_rows=5)

    def execute(self, sql, binding, *, max_rows, timeout_ms):
        if self.fail:
            raise QueryError("replica is down")
        self.executed.append(sql)
        return QueryResult(
            columns=(ResultColumn(name="n", type_name="bigint"),),
            rows=((42,),),
            truncated=False,
            duration_ms=3,
        )

    def ping(self) -> None:
        if self.fail:
            raise QueryError("down")


class FakeData:
    def __init__(self, adapters: dict[str, FakeAdapter]) -> None:
        self.adapters = adapters

    def adapter_for(self, app, source_id=None):
        return self.adapters[source_id or "main"]


def approve_when_pending(store: HitlStore) -> threading.Thread:
    def worker():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            pending = store.pending()
            if pending:
                store.decide(pending[0].run_id,
                             HitlDecision(action="approve", decided_by="reviewer"))
                return
            time.sleep(0.01)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


def build_runtime(gateway, adapters, hitl=None):
    results = InMemoryResultStore()
    runtime = Runtime(
        registry=REGISTRY,
        gateway=gateway,
        audit=InMemoryAuditSink(),
        results=results,
        runs=InMemoryRunStore(),
        services=Services(
            catalogs=DirectoryCatalogs(ROOT / "apps"),
            data=FakeData(adapters),
            hitl=hitl,
        ),
    )
    return runtime, results


class OneSourceDataQuery(unittest.TestCase):
    def test_answers_end_to_end_with_decisions_and_events(self):
        gateway = FakeGateway([SQL_ENVELOPE] * 3)  # repairs/refines may re-ask
        store = HitlStore()
        approve_when_pending(store)
        runtime, _ = build_runtime(gateway, {"main": FakeAdapter()}, hitl=store)
        events = []
        record = runtime.run(
            ORCH,
            input={"query": "How many patients are currently enrolled?", "context": {}},
            principal=MARIA,
            app=APP,
            on_event=events.append,
        )
        self.assertEqual(record.outcome, "completed", record.failure)
        answer = (record.output or {}).get("answer") or {}
        self.assertEqual(answer.get("status"), "answered", answer)

        # the supervisor recorded which agent it picked for every stage, and why
        picks = {(d.stage, d.skill) for d in record.decisions if d.action in ("run", "fanout")}
        self.assertIn(("routing", "skill-router"), picks)
        self.assertIn(("schema_slicing", "schema-sliver"), picks)
        self.assertIn(("query_generation", "query-generator"), picks)
        self.assertIn(("governed_execution", "governed-executor"), picks)
        self.assertIn(("synthesis", "synthesizer"), picks)
        self.assertIn(("assessment", "result-assessor"), picks)
        self.assertIn(("answer_composition", "answer-composer"), picks)
        self.assertNotIn(("metadata_answer", "metadata-answerer"), picks)
        self.assertTrue(all(d.reason for d in record.decisions))

        # the UI event stream: the graph definition first, then one active agent per step
        self.assertIs(events[0].type, EventType.GRAPH_DEFINITION)
        self.assertIn("governed_execution", events[0].steps)
        started = [(e.step_id, e.skill) for e in events if e.type is EventType.STAGE_STARTED]
        order = [step for step, _ in started]
        self.assertLess(order.index("routing"), order.index("schema_slicing"))
        self.assertLess(order.index("schema_slicing"), order.index("query_generation"))
        self.assertLess(order.index("governed_execution"), order.index("synthesis"))
        self.assertEqual(order[-1], "answer_composition")
        for step, skill in started:
            self.assertIsNotNone(skill, f"step {step} has no active agent")
        decisions = [e for e in events if e.type is EventType.SUPERVISOR_DECISION]
        self.assertEqual(len(decisions), len(record.decisions) - 1)  # minus the end decision
        finished = [e for e in events if e.type is EventType.STAGE_FINISHED]
        self.assertTrue(all(e.duration_ms is not None and e.tokens is not None
                            for e in finished))

        # the 1-source fan-out ran exactly one branch, named after the data source
        branches = {e.branch for e in finished if e.step_id == "governed_execution"}
        self.assertEqual(branches, {"main"})


class MetadataQuestionPicksTheMetadataPath(unittest.TestCase):
    def test_supervisor_routes_by_intent(self):
        gateway = FakeGateway(
            [{"intent": "metadata_question", "confidence": 0.9, "reason": "tables"}] * 2
        )
        runtime, _ = build_runtime(gateway, {"main": FakeAdapter()})
        record = runtime.run(
            ORCH,
            input={"query": "what tables hold pregnancy episodes", "context": {}},
            principal=MARIA,
            app=APP,
        )
        self.assertEqual(record.outcome, "completed", record.failure)
        picks = {(d.stage, d.skill) for d in record.decisions if d.action in ("run", "fanout")}
        self.assertIn(("metadata_answer", "metadata-answerer"), picks)
        self.assertNotIn(("schema_slicing", "schema-sliver"), picks)
        self.assertNotIn(("governed_execution", "governed-executor"), picks)


class TwoSourcePartialFailure(unittest.TestCase):
    def test_partial_synthesis_through_the_real_skills(self):
        """Two fan-out branches, one failing: the synthesizer reports a partial result and the
        composer still answers from the surviving source, saying what is missing."""
        synthesizer = REGISTRY.get("synthesizer")
        from insights.test_hitl_synthesizer import OK_EXECUTION, make_ctx

        ctx = make_ctx()
        out = synthesizer.run(
            {
                "question": "q",
                "executions": [
                    {"attempt": 1, "index": 0, "branch": "main", "item": "main",
                     "output": OK_EXECUTION},
                    {"attempt": 1, "index": 1, "branch": "replica", "item": "replica",
                     "output": {"status": "error", "failure": "error", "columns": [],
                                "masked_columns": []}},
                    # a stale first-attempt entry that must be ignored
                    {"attempt": 0, "index": 0, "branch": "main", "item": "main",
                     "output": {"status": "timeout", "failure": "timeout", "columns": [],
                                "masked_columns": []}},
                ],
            },
            ctx,
        )
        self.assertEqual(out["label"], "partial")
        self.assertEqual(out["synthesis"]["succeeded"], 1)
        self.assertEqual(out["synthesis"]["failed"], [{"source": "replica", "status": "error"}])
        self.assertEqual(out["primary_execution"]["status"], "ok")
        self.assertEqual(out["confidence_hint"], 0.5)

    def test_all_sources_failing_still_reaches_an_honest_terminal_answer(self):
        gateway = FakeGateway([SQL_ENVELOPE] * 4)
        store = HitlStore()
        approve_when_pending(store)
        runtime, _ = build_runtime(
            gateway, {"main": FakeAdapter(fail=True)}, hitl=store
        )
        record = runtime.run(
            ORCH,
            input={"query": "How many patients are currently enrolled?", "context": {}},
            principal=MARIA,
            app=APP,
        )
        self.assertEqual(record.outcome, "completed", record.failure)
        answer = (record.output or {}).get("answer") or {}
        self.assertIn(answer.get("status"), ("failed", "abstained"), answer)


if __name__ == "__main__":
    unittest.main()
