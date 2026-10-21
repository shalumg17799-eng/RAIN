"""The two new insights skills: the synthesizer's merge and the hitl-reviewer's gate and wait."""

import threading
import time
import unittest
from pathlib import Path

from insights.contracts.enums import AuditEventType, EventType, Purpose
from insights.contracts.principal import Principal
from insights.contracts.profile import ModelPolicy, load_app_profile
from insights.gateway.base import GatewayError
from insights.runtime.events import EventEmitter
from insights.runtime.hitl import HitlDecision, HitlStore
from insights.runtime.stores import InMemoryAuditSink, InMemoryResultStore, MonotonicDeadline, TokenMeter
from insights.runtime.test_skill_agent import FakeGateway
from insights.skills_core.protocols import Services
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = SkillRegistry.scan(ROOT / "skills")
APP = load_app_profile(ROOT / "apps" / "rain" / "app.yaml")

OK_EXECUTION = {
    "status": "ok", "row_count": 4, "truncated": False, "result_ref": None,
    "columns": [{"name": "county", "type": "text"}, {"name": "n", "type": "bigint"}],
    "masked_columns": [],
}
FAILED_EXECUTION = {"status": "timeout", "failure": "timeout", "columns": [], "masked_columns": []}


def make_ctx(gateway=None, *, services=None, deadline_ms=60_000, events=None, app=APP):
    return {
        "run_id": "run-hitl-1",
        "trace_id": "b" * 32,
        "step_id": "hitl_review",
        "attempt": 0,
        "app": app,
        "principal": Principal(
            subject="svc-test", tenant="svc-internal", roles=("maria",),
            entitlement_digest="0" * 64,
        ),
        "usage": TokenMeter(),
        "deadline": MonotonicDeadline(time.monotonic, deadline_ms),
        "emit": lambda note, count=None: None,
        "gateway": gateway or FakeGateway([]),
        "services": services or Services(),
        "results": InMemoryResultStore(),
        "audit": InMemoryAuditSink(),
        "events": events,
    }


class SynthesizerTests(unittest.TestCase):
    def run_skill(self, input, ctx=None):
        return REGISTRY.get("synthesizer").run(input, ctx or make_ctx())

    def test_single_source_is_ok(self):
        out = self.run_skill({"question": "q", "execution": OK_EXECUTION})
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["synthesis"]["succeeded"], 1)
        self.assertEqual(out["confidence_hint"], 1.0)

    def test_two_sources_with_one_failure_is_partial(self):
        out = self.run_skill({
            "question": "q",
            "executions": [
                {"source": "pg_main", "execution": OK_EXECUTION},
                {"source": "pg_replica", "execution": FAILED_EXECUTION},
            ],
        })
        self.assertEqual(out["label"], "partial")
        self.assertTrue(out["synthesis"]["partial"])
        self.assertEqual(out["synthesis"]["failed"], [{"source": "pg_replica", "status": "timeout"}])
        self.assertEqual(out["confidence_hint"], 0.5)

    def test_every_source_failing_is_all_failed(self):
        out = self.run_skill({
            "question": "q",
            "executions": [{"source": "a", "execution": FAILED_EXECUTION}],
        })
        self.assertEqual(out["label"], "all_failed")
        self.assertEqual(out["confidence_hint"], 0.0)

    def test_rows_anywhere_in_the_input_are_refused(self):
        with self.assertRaises(ValueError):
            self.run_skill({
                "question": "q",
                "execution": {**OK_EXECUTION, "rows": [["secret"]]},
            })

    def test_cross_source_note_uses_narrate_and_survives_gateway_failure(self):
        app = APP.model_copy(update={"model_policy": {
            **APP.model_policy,
            Purpose.NARRATE: ModelPolicy(enabled=True, model_group="fast",
                                         temperature=0.0, max_tokens=200),
        }})
        gateway = FakeGateway(["Both sources agree on 4 rows."])
        out = self.run_skill(
            {"question": "q", "executions": [
                {"source": "a", "execution": OK_EXECUTION},
                {"source": "b", "execution": OK_EXECUTION},
            ]},
            make_ctx(gateway, app=app),
        )
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["synthesis"]["note"], "Both sources agree on 4 rows.")
        self.assertEqual(gateway.calls[0]["purpose"], Purpose.NARRATE)
        for message in gateway.calls[0]["messages"]:
            self.assertNotIn("rows=[[", message.content)

        failing = FakeGateway([GatewayError("down")])
        out = self.run_skill(
            {"question": "q", "executions": [
                {"source": "a", "execution": OK_EXECUTION},
                {"source": "b", "execution": OK_EXECUTION},
            ]},
            make_ctx(failing, app=app),
        )
        self.assertEqual(out["label"], "ok")
        self.assertIsNone(out["synthesis"]["note"])


class HitlReviewerTests(unittest.TestCase):
    def run_skill(self, input, ctx):
        return REGISTRY.get("hitl-reviewer").run(input, ctx)

    def decide_when_pending(self, store, decision):
        def worker():
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if store.pending():
                    store.decide(store.pending()[0].run_id, decision)
                    return
                time.sleep(0.01)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    def test_confident_clean_answer_is_clear(self):
        out = self.run_skill(
            {"question": "q", "assessment": {"confidence": 0.9, "label": "answer"},
             "execution": OK_EXECUTION},
            make_ctx(services=Services(hitl=HitlStore())),
        )
        self.assertEqual(out["label"], "clear")
        self.assertFalse(out["hitl_review"]["held"])

    def test_low_confidence_hold_resolves_as_approved_and_is_audited(self):
        store = HitlStore()
        events: list = []
        ctx = make_ctx(services=Services(hitl=store),
                       events=EventEmitter([events.append], "run-hitl-1"))
        self.decide_when_pending(store, HitlDecision(action="approve", decided_by="maria"))
        out = self.run_skill(
            {"question": "q", "assessment": {"confidence": 0.2, "label": "answer"},
             "generation": {"sql": "SELECT 1"}},
            ctx,
        )
        self.assertEqual(out["label"], "approved")
        self.assertEqual(out["hitl_review"]["reason"], "low_confidence")
        self.assertEqual(out["hitl_review"]["decided_by"], "maria")
        kinds = [e.type for e in events]
        self.assertIn(EventType.HITL_WAITING, kinds)
        self.assertIn(EventType.HITL_DECIDED, kinds)
        audit_types = [e.type for e in ctx["audit"].events()]
        self.assertIn(AuditEventType.HITL_DECISION, audit_types)

    def test_edit_carries_the_edited_narrative(self):
        store = HitlStore()
        ctx = make_ctx(services=Services(hitl=store))
        self.decide_when_pending(
            store, HitlDecision(action="edit", decided_by="maria",
                                edited_narrative="Verified: 4 rows, trend is stable."),
        )
        out = self.run_skill(
            {"question": "q", "assessment": {"confidence": 0.2}}, ctx
        )
        self.assertEqual(out["label"], "edited")
        self.assertEqual(out["hitl_review"]["edited_narrative"],
                         "Verified: 4 rows, trend is stable.")

    def test_reject_resolves_as_rejected(self):
        store = HitlStore()
        ctx = make_ctx(services=Services(hitl=store))
        self.decide_when_pending(store, HitlDecision(action="reject", decided_by="maria"))
        out = self.run_skill({"question": "q", "assessment": {"confidence": 0.1}}, ctx)
        self.assertEqual(out["label"], "rejected")

    def test_no_decision_times_out(self):
        store = HitlStore()
        ctx = make_ctx(services=Services(hitl=store), deadline_ms=300)
        started = time.monotonic()
        out = self.run_skill({"question": "q", "assessment": {"confidence": 0.1}}, ctx)
        self.assertEqual(out["label"], "timeout")
        self.assertLess(time.monotonic() - started, 5)

    def test_sensitive_intent_and_governance_flags_hold(self):
        ctx = make_ctx(deadline_ms=100)  # no store: fails closed as timeout
        out = self.run_skill(
            {"question": "q", "assessment": {"confidence": 0.9},
             "route": {"screening": {"injection_suspected": True}}},
            ctx,
        )
        self.assertEqual(out["hitl_review"]["reason"], "sensitive_intent")
        self.assertEqual(out["label"], "timeout")

        out = self.run_skill(
            {"question": "q", "assessment": {"confidence": 0.9},
             "execution": {**OK_EXECUTION, "masked_columns": ["ssn"]}},
            make_ctx(deadline_ms=100),
        )
        self.assertEqual(out["hitl_review"]["reason"], "governance_flag")

        out = self.run_skill(
            {"question": "q", "assessment": {"confidence": 0.9},
             "synthesis": {"partial": True}},
            make_ctx(deadline_ms=100),
        )
        self.assertEqual(out["hitl_review"]["reason"], "governance_flag")


class HitlStoreTests(unittest.TestCase):
    def test_decide_unknown_run_is_a_noop(self):
        store = HitlStore()
        self.assertFalse(store.decide("nope", HitlDecision(action="approve", decided_by="x")))

    def test_edit_requires_narrative(self):
        with self.assertRaises(ValueError):
            HitlDecision(action="edit", decided_by="x")

    def test_pending_lists_only_undecided_holds(self):
        store = HitlStore()
        store.hold(run_id="r1", trace_id="t", reason="low_confidence", question="q")
        self.assertEqual(len(store.pending()), 1)
        store.decide("r1", HitlDecision(action="approve", decided_by="x"))
        self.assertEqual(store.pending(), [])
        self.assertEqual(store.wait("r1", 0.1).action, "approve")


if __name__ == "__main__":
    unittest.main()
