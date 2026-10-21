"""The supervisor: agent selection against the real registry, and a full graph run on a fake pack.

Part 1 exercises `choose_next` as the pure function it is, against the REAL insights pack: the
right agent per query type, loop-backs, terminal labels, exhaustion — no gateway, no services.
Part 2 compiles a supervisor graph over a small temporary pack and runs it end to end: forward
progress by capabilities, a bounded refine loop, per-item fan-out, decisions and typed events.
"""

import tempfile
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

from insights.contracts.enums import EventType
from insights.contracts.orchestrator import FanoutDef, OrchestratorDef, StageDef, SupervisorLimits
from insights.contracts.principal import Principal
from insights.contracts.profile import load_app_profile
from insights.runtime.events import EventEmitter
from insights.runtime.graph import build_supervisor_graph
from insights.runtime.limits import EffectiveLimits
from insights.runtime.scope import RunScope
from insights.runtime.stores import (
    InMemoryAuditSink,
    InMemoryResultStore,
    MonotonicDeadline,
    TokenMeter,
)
from insights.runtime.supervisor import (
    choose_next,
    load_orchestrator,
    registry_views,
    validate_orchestrator,
)
from insights.skills_core.protocols import Services
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = SkillRegistry.scan(ROOT / "skills")
ORCH = load_orchestrator(ROOT / "agents" / "insights" / "orchestrator.yaml")
VIEWS = registry_views(REGISTRY, "insights")
APP = load_app_profile(ROOT / "apps" / "rain" / "app.yaml")


def fresh_state(**overrides):
    state = {
        "input": {"query": "q", "context": {}},
        "steps": {},
        "exec_counts": {},
        "refine": {"attempt": 0, "max_refines": 2, "critique": None, "history": [],
                   "exhausted": False, "tokens_used": 0},
        "trace": [],
        "fanout": {},
        "failure": None,
        "decisions": [],
        "needed_runs": {},
    }
    state.update(overrides)
    return state


def ran(state, stage, skill, output, *, action="run"):
    """Record a finished stage run plus the decision that routed there."""
    state["steps"][stage] = {"skill": skill, "version": "1.0.0", "output": output,
                             "label": None, "runs": state["exec_counts"].get(stage, 0) + 1}
    state["exec_counts"][stage] = state["exec_counts"].get(stage, 0) + 1
    state["decisions"].append({"seq": len(state["decisions"]) + 1, "action": action,
                               "stage": stage, "skill": skill, "reason": "artifact_missing",
                               "considered": [skill], "detail": {}})
    return state


def routed(intent, label=None):
    state = fresh_state()
    return ran(state, "routing", "skill-router",
               {"label": label or intent, "intent": intent, "path_preference": "bypass"})


class ChooseNextAgainstTheRealPack(unittest.TestCase):
    def test_orchestrator_validates_against_the_registry(self):
        self.assertEqual(validate_orchestrator(ORCH, REGISTRY), [])

    def test_first_decision_is_the_router(self):
        decision = choose_next(ORCH, VIEWS, fresh_state(), source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual((decision.stage, decision.skill), ("routing", "skill-router"))
        self.assertEqual(decision.reason, "artifact_missing")

    def test_metadata_question_picks_the_metadata_answerer_not_the_sliver(self):
        decision = choose_next(ORCH, VIEWS, routed("metadata_question"),
                               source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual((decision.stage, decision.skill), ("metadata_answer", "metadata-answerer"))
        self.assertEqual(decision.reason, "intent_match")

    def test_data_query_picks_the_schema_sliver(self):
        decision = choose_next(ORCH, VIEWS, routed("data_query"), source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual((decision.stage, decision.skill), ("schema_slicing", "schema-sliver"))

    def test_out_of_scope_goes_straight_to_the_composer(self):
        state = routed("out_of_scope", label="out_of_scope")
        decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual((decision.stage, decision.skill),
                         ("answer_composition", "answer-composer"))
        self.assertEqual(decision.reason, "escalation")

    def test_the_full_data_chain_advances_stage_by_stage(self):
        state = routed("data_query")
        chain = [
            ("schema_slicing", "schema-sliver", {"label": "ok", "sliver": {}, "concepts": []}),
            ("query_generation", "query-generator", {"label": "generated", "sql": "SELECT 1"}),
            ("governed_execution", "governed-executor", {"label": "ok", "status": "ok"}),
            ("synthesis", "synthesizer", {"label": "ok", "synthesis": {}}),
            ("assessment", "result-assessor", {"label": "answer", "confidence": 0.9}),
            ("hitl_review", "hitl-reviewer", {"label": "clear", "hitl_review": {}}),
        ]
        for expected_stage, expected_skill, output in chain:
            decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
            self.assertEqual((decision.stage, decision.skill), (expected_stage, expected_skill))
            ran(state, expected_stage, expected_skill, output)
        decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual(decision.stage, "answer_composition")
        self.assertEqual(decision.reason, "pipeline_complete")
        ran(state, "answer_composition", "answer-composer", {"status": "answered"})
        self.assertEqual(choose_next(ORCH, VIEWS, state).reason, "goal_reached")

    def data_state_through_assessment(self, assess_output):
        state = routed("data_query")
        ran(state, "schema_slicing", "schema-sliver", {"label": "ok", "sliver": {}, "concepts": []})
        ran(state, "query_generation", "query-generator", {"label": "generated", "sql": "SELECT 1"})
        ran(state, "governed_execution", "governed-executor", {"label": "ok", "status": "ok"})
        ran(state, "synthesis", "synthesizer", {"label": "ok", "synthesis": {}})
        ran(state, "assessment", "result-assessor", assess_output)
        return state

    def test_refine_query_loops_back_to_the_query_generator(self):
        state = self.data_state_through_assessment(
            {"label": "refine_query", "critique": "counts the wrong thing"}
        )
        decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual(decision.reason, "refine_requested")
        self.assertEqual((decision.stage, decision.skill), ("query_generation", "query-generator"))
        self.assertEqual(decision.detail["from_stage"], "assessment")

    def test_refine_sliver_loops_back_to_the_schema_sliver(self):
        state = self.data_state_through_assessment({"label": "refine_sliver", "critique": "widen"})
        decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual((decision.stage, decision.skill), ("schema_slicing", "schema-sliver"))

    def test_exhausted_refines_continue_to_the_hitl_gate(self):
        # the insights posture: one refine too many flows ON to human review, not to abstention
        state = self.data_state_through_assessment({"label": "refine_query", "critique": "x"})
        state["refine"]["attempt"] = 2  # == max_refines
        decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual(decision.stage, "hitl_review")
        self.assertEqual(decision.reason, "refines_exhausted")

    def test_execution_fans_out_per_source_and_escalation_is_terminal(self):
        state = routed("data_query")
        ran(state, "schema_slicing", "schema-sliver",
            {"label": "ok", "sliver": {}, "concepts": [], "sources": ["main"]})
        ran(state, "query_generation", "query-generator", {"label": "generated", "sql": "SELECT 1"})
        decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual(decision.action, "fanout")
        self.assertEqual((decision.stage, decision.skill),
                         ("governed_execution", "governed-executor"))
        # a refused execution surfaces through the assessor, whose escalation is terminal
        state = self.data_state_through_assessment(
            {"label": "escalate", "critique": "the query was refused (policy_denied)"}
        )
        decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual(decision.stage, "answer_composition")
        self.assertEqual(decision.reason, "escalation")
        self.assertEqual(decision.detail["label"], "escalate")

    def test_hitl_rejection_is_terminal(self):
        state = self.data_state_through_assessment({"label": "answer", "confidence": 0.9})
        ran(state, "hitl_review", "hitl-reviewer", {"label": "rejected", "hitl_review": {}})
        decision = choose_next(ORCH, VIEWS, state, source_types=("postgres", "catalog", "knowledge_graph"))
        self.assertEqual(decision.stage, "answer_composition")
        self.assertEqual(decision.reason, "escalation")

    def test_run_failure_ends_the_run(self):
        state = fresh_state(failure={"reason": "deadline", "step_id": None, "message": "x"})
        self.assertEqual(choose_next(ORCH, VIEWS, state).action, "end")


# ---- part 2: a real graph run over a small fake pack -----------------------------------------

FAKE_SKILLS = {
    "router-stub": {
        "stage": "routing",
        "labels": "[data_query, out_of_scope]",
        "caps": "capabilities:\n  produces: [route]",
        "body": '''
def run(input, ctx):
    query = input.get("query") or ""
    intent = "out_of_scope" if "weather" in query else "data_query"
    items = ["branch_a", "branch_b"]
    return {"label": intent, "intent": intent, "items": items}
''',
    },
    "worker-stub": {
        "stage": "work",
        "labels": "[ok, refine_self]",
        "caps": "capabilities:\n  intents: [data_query]\n  consumes: [route]\n  produces: [work]",
        "body": '''
def run(input, ctx):
    attempt = int(input.get("attempt") or 0)
    if attempt == 0:
        return {"label": "refine_self", "critique": "try harder", "work": None}
    return {"label": "ok", "work": {"attempt": attempt}, "critique": None}
''',
    },
    "fan-stub": {
        "stage": "fan",
        "labels": "[ok]",
        "caps": "capabilities:\n  intents: [data_query]\n  consumes: [work]\n  produces: [fan_items]",
        "body": '''
def run(input, ctx):
    return {"label": "ok", "piece": {"branch": input.get("branch")}}
''',
    },
    "reduce-stub": {
        "stage": "reduce",
        "labels": "[ok]",
        "caps": "capabilities:\n  intents: [data_query]\n  consumes: [fanout_fan]\n  produces: [reduced]",
        "body": '''
def run(input, ctx):
    entries = input.get("results") or []
    return {"label": "ok", "reduced": {"count": len(entries)}}
''',
    },
    "composer-stub": {
        "stage": "composition",
        "labels": "[]",
        "caps": "capabilities:\n  produces: [answer]",
        "body": '''
def run(input, ctx):
    steps = input.get("steps") or {}
    return {"status": "done", "stages_seen": sorted(steps)}
''',
    },
}

FAKE_ORCH = OrchestratorDef(
    name="fake-orchestrator",
    version="1.0.0",
    pack="insights",
    stages=(
        StageDef(stage="routing", input={"query": "$.input.query"},
                 terminal_labels=("out_of_scope",)),
        StageDef(stage="work", input={"attempt": "$.refine.attempt",
                                      "critique": "$.refine.critique"}),
        StageDef(stage="fan", input={},
                 fanout=FanoutDef(over="$.steps.routing.output.items", item_key="branch")),
        StageDef(stage="reduce", input={"results": "$.fanout.fan"}),
        StageDef(stage="composition", input={"steps": "$.steps"}, terminal=True),
    ),
    output={"answer": "$.steps.composition.output"},
    limits=SupervisorLimits(max_refines=2, max_steps=12, max_tokens=100000, deadline_ms=60000),
)


def write_fake_pack(root: Path) -> None:
    for name, spec in FAKE_SKILLS.items():
        folder = root / "insights" / name
        (folder / "scripts").mkdir(parents=True)
        caps = spec["caps"].replace("\n", "\n") + "\n" if spec["caps"] else ""
        (folder / "SKILL.md").write_text(
            "---\n"
            f"name: {name}\nversion: 1.0.0\ndescription: stub\npack: insights\n"
            f"stage: {spec['stage']}\nkind: deterministic\n{caps}"
            f"labels: {spec['labels']}\n---\nstub body\n",
            encoding="utf-8",
        )
        (folder / "scripts" / "run.py").write_text(spec["body"], encoding="utf-8")


class SupervisorGraphRunTests(unittest.TestCase):
    def run_graph(self, query: str):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        write_fake_pack(root)
        registry = SkillRegistry.scan(root)
        self.assertEqual(registry.errors, (), registry.errors)
        events = []
        scope = RunScope(
            run_id="sup-run-1",
            trace_id="c" * 32,
            thread_id="sup-run-1",
            registry=registry,
            gateway=None,
            audit=InMemoryAuditSink(),
            results=InMemoryResultStore(),
            meter=TokenMeter(),
            deadline=MonotonicDeadline(time.monotonic, 60_000),
            emitter=EventEmitter([events.append], "sup-run-1"),
            principal=Principal(subject="svc-test", tenant="svc-internal", roles=(),
                                entitlement_digest="0" * 64),
            app=APP,
            limits=EffectiveLimits(max_refines=2, max_tokens=100000, deadline_ms=60000),
            clock=time.monotonic,
            now=lambda: datetime.now(UTC),
            services=Services(),
        )
        compiled = build_supervisor_graph(FAKE_ORCH, registry)
        initial = fresh_state(input={"query": query, "context": {}})
        outcome = compiled.execute(initial, scope, 48)
        self.addCleanup(self.tmp.cleanup)
        return outcome, events

    def test_full_run_with_refine_loop_and_fanout(self):
        outcome, events = self.run_graph("how many patients")
        state = outcome.state
        self.assertIsNone(outcome.error)
        self.assertIsNone(state.get("failure"))

        # the supervisor recorded why it picked every agent
        decisions = state["decisions"]
        picks = [(d["stage"], d["reason"]) for d in decisions if d["action"] != "end"]
        self.assertEqual(picks[0], ("routing", "artifact_missing"))
        self.assertIn(("work", "refine_requested"), picks)
        self.assertIn(("fan", "fanout_dispatch"), picks)
        self.assertEqual(decisions[-1]["reason"], "goal_reached")

        # the refine loop ran the worker twice, bounded
        self.assertEqual(state["exec_counts"]["work"], 2)
        self.assertEqual(state["refine"]["attempt"], 1)
        self.assertEqual(state["steps"]["work"]["output"]["label"], "ok")

        # fan-out produced one entry per item, and the reducer saw both
        fan_entries = state["fanout"]["fan"]
        self.assertEqual(len(fan_entries), 2)
        self.assertEqual({e["branch"] for e in fan_entries}, {"branch_a", "branch_b"})
        self.assertEqual(state["steps"]["reduce"]["output"]["reduced"]["count"], 2)

        # the terminal composer ran last and saw the finished stages
        self.assertIn("reduce", state["steps"]["composition"]["output"]["stages_seen"])

        # typed decision events for the UI, with branch identities on the fan-out
        decision_events = [e for e in events if e.type is EventType.SUPERVISOR_DECISION]
        self.assertGreaterEqual(len(decision_events), 5)
        self.assertTrue(all(e.reason and e.skill and e.stage for e in decision_events))
        branch_events = [e for e in events
                         if e.type is EventType.STAGE_FINISHED and e.branch is not None]
        self.assertEqual({e.branch for e in branch_events}, {"branch_a", "branch_b"})

    def test_terminal_label_short_circuits_to_the_composer(self):
        outcome, _ = self.run_graph("what is the weather")
        state = outcome.state
        self.assertIsNone(state.get("failure"))
        self.assertNotIn("work", state["steps"])  # the data chain never ran
        self.assertNotIn("fan", state["steps"])
        reasons = [d["reason"] for d in state["decisions"]]
        self.assertIn("escalation", reasons)
        self.assertIn("composition", state["steps"])


if __name__ == "__main__":
    unittest.main()
