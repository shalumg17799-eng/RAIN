"""NLQ skill-agent upgrades (slice 9): the query-generator's loop on the shared runtime, the
assessor's bounded judge, and the invariants both must keep (same output contracts, honest
model_unavailable, the judge never sees rows)."""

import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from insights.contracts.enums import Purpose
from insights.contracts.principal import Principal
from insights.contracts.profile import ModelPolicy, load_app_profile
from insights.gateway.base import ModelUnavailableError
from insights.runtime.stores import InMemoryResultStore, MonotonicDeadline, TokenMeter
from insights.runtime.test_skill_agent import FakeGateway
from insights.skills_core.protocols import Services
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = SkillRegistry.scan(ROOT / "skills")
APP = load_app_profile(ROOT / "apps" / "rain" / "app.yaml")

SLIVER = {
    "tables": [
        {"source_id": "main", "name": "Patient",
         "columns": [{"name": "patient_id", "type": "text"}, {"name": "county", "type": "text"}]},
    ],
    "joins": [],
    "glossary_terms": [],
    "coverage": 1.0,
    "path_used": "bypass",
    "catalog_version": "0" * 64,
}


class FakeCatalogs:
    def for_app(self, app):
        return SimpleNamespace(
            catalog=SimpleNamespace(
                examples=(), vocabulary=frozenset(),
                glossary=SimpleNamespace(terms=[]),
            )
        )


def make_ctx(gateway, app=APP):
    return {
        "run_id": "run1",
        "trace_id": "a" * 32,
        "step_id": "generate",
        "attempt": 0,
        "app": app,
        "principal": Principal(
            subject="svc-test", tenant="svc-internal", roles=("maria",),
            entitlement_digest="0" * 64,
        ),
        "usage": TokenMeter(),
        "deadline": MonotonicDeadline(time.monotonic, 60_000),
        "emit": lambda note, count=None: None,
        "gateway": gateway,
        "services": Services(catalogs=FakeCatalogs()),
        "results": InMemoryResultStore(),
        "audit": None,
    }


def run_generator(gateway, **extra):
    skill = REGISTRY.get("query-generator")
    input = {"query": "How many patients per county?", "sliver": SLIVER, **extra}
    return skill.run(input, make_ctx(gateway))


class QueryGeneratorAgentTests(unittest.TestCase):
    def test_grounded_sql_is_generated_first_try(self):
        gateway = FakeGateway([
            {"action": "finish",
             "result": {"sql": "SELECT county, count(*) FROM Patient GROUP BY county",
                        "assumptions": [], "tables_used": ["patient"]},
             "confidence": 0.9},
        ])
        out = run_generator(gateway)
        self.assertEqual(out["label"], "generated")
        self.assertEqual(out["repairs"], 0)
        self.assertEqual(out["tables_used"], ["patient"])
        self.assertEqual(gateway.calls[0]["purpose"], Purpose.SQL)

    def test_ungrounded_sql_is_semantically_repaired(self):
        gateway = FakeGateway([
            {"action": "finish",
             "result": {"sql": "SELECT count(*) FROM Ghosts", "assumptions": [],
                        "tables_used": ["ghosts"]},
             "confidence": 0.9},
            {"action": "finish",
             "result": {"sql": "SELECT count(*) FROM Patient", "assumptions": [],
                        "tables_used": ["patient"]},
             "confidence": 0.9},
        ])
        out = run_generator(gateway)
        self.assertEqual(out["label"], "generated")
        self.assertEqual(out["repairs"], 1)
        repair = gateway.calls[1]["messages"][-1].content
        self.assertIn("not in the schema sliver", repair)

    def test_validate_sql_tool_is_available_to_the_model(self):
        gateway = FakeGateway([
            {"action": "use_tool", "tool": "validate_sql",
             "tool_args": {"sql": "SELECT count(*) FROM Patient"}},
            {"action": "finish",
             "result": {"sql": "SELECT count(*) FROM Patient", "assumptions": [],
                        "tables_used": ["patient"]},
             "confidence": 0.9},
        ])
        out = run_generator(gateway)
        self.assertEqual(out["label"], "generated")
        observation = gateway.calls[1]["messages"][-1].content
        self.assertIn('"grounded": true', observation)

    def test_no_model_stays_an_honest_failure(self):
        gateway = FakeGateway([ModelUnavailableError("no model configured")])
        out = run_generator(gateway)
        self.assertEqual(out["label"], "unusable")
        self.assertEqual(out["reason"], "model_unavailable")

    def test_empty_sliver_is_unusable_without_any_model_call(self):
        gateway = FakeGateway([])
        out = run_generator(gateway, sliver={**SLIVER, "tables": []})
        self.assertEqual(out["label"], "unusable")
        self.assertEqual(out["reason"], "empty_sliver")
        self.assertEqual(gateway.calls, [])


class ResultAssessorJudgeTests(unittest.TestCase):
    def app_with_judge(self):
        return APP.model_copy(update={
            "model_policy": {
                **APP.model_policy,
                Purpose.JUDGE: ModelPolicy(
                    enabled=True, model_group="fast", temperature=0.0, max_tokens=200
                ),
            }
        })

    def run_assessor(self, gateway, app):
        skill = REGISTRY.get("result-assessor")
        ctx = make_ctx(gateway, app=app)
        execution = {
            "status": "ok", "row_count": 3, "truncated": False, "result_ref": None,
            "columns": [{"name": "county", "type": "text"}, {"name": "n", "type": "bigint"}],
        }
        return skill.run(
            {"question": "How many patients per county?", "execution": execution,
             "sliver": SLIVER, "generation": {"sql": "SELECT 1", "repairs": 0}, "attempt": 0},
            ctx,
        )

    def test_judge_disagreement_routes_to_refine_query_with_the_reason(self):
        gateway = FakeGateway([
            {"action": "finish",
             "result": {"agrees": False, "issue": "counts facilities, not patients"},
             "confidence": 0.9},
        ])
        out = self.run_assessor(gateway, self.app_with_judge())
        self.assertEqual(out["label"], "refine_query")
        self.assertIn("counts facilities", out["critique"])
        # the judge saw shape only: no message may carry a value from any row
        for call in gateway.calls:
            for message in call["messages"]:
                self.assertNotIn("contains_rows=True", message.content)
                self.assertFalse(message.contains_rows)

    def test_disabled_judge_answers_without_a_model_call(self):
        gateway = FakeGateway([])
        out = self.run_assessor(gateway, APP)  # rain profile ships judge disabled
        self.assertEqual(out["label"], "answer")
        self.assertEqual(gateway.calls, [])


if __name__ == "__main__":
    unittest.main()
