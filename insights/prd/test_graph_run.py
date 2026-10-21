"""End-to-end tests of the PRD pipeline (agents/data/orchestrator.yaml) through PrdRunner.

Only the model is faked: the real registry, real skills, real validators, real reducers, the real
LangGraph compilation with Send fan-out, and the real SQLite checkpointer all run. The fake
gateway routes by prompt content, so parallel fan-out items are order-independent.
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from insights.contracts.gateway import CompletionResult, Usage
from insights.contracts.principal import Principal
from insights.contracts.profile import load_app_profile
from insights.prd.runner import PrdRunner
from insights.runtime.stores import TokenMeter

ROOT = Path(__file__).resolve().parents[2]

PRD_TEXT = """RAIN Prototype Spec

Overview
This morning the clinic saw a spike. Dr. Maria Delgado-Reyes oversees 38 pregnant patients.
James coordinates EMS transport across 5 counties.
"""

IR = {
    "mode": "persona_questions",
    "domain": "rural health",
    "anchor_date": "2026-03-01",
    "personas": [
        {"id": "maria", "name": "Maria", "role": "Medical Director", "altitude": "executive",
         "problems": ["maternal access"], "systems": ["Clinical EHR"]},
        {"id": "james", "name": "James", "role": "EMS Coordinator", "altitude": "operational",
         "problems": ["transport load"], "systems": ["EMS Dispatch"]},
    ],
    "questions": [
        {"id": "Q1", "persona_id": "maria", "text": "How many pregnant patients are overdue?",
         "tier": "extracted", "is_data_question": True},
        {"id": "Q2", "persona_id": "james", "text": "How many transports ran today?",
         "tier": "extracted", "is_data_question": True},
    ],
    "committed_figures": [{"id": "F1", "value": "38", "tolerance": "exact"}],
    "source_systems": [], "entity_hints": [], "narrative_events": [],
    "constraints": [], "open_items": [],
}

QUESTIONS = {
    "maria": {"questions": [
        {"persona_id": "maria", "text": "How many pregnant patients are overdue?",
         "tier": "extracted", "signal": "overdue count", "is_data_question": True},
    ]},
    "james": {"questions": [
        {"persona_id": "james", "text": "How many transports ran today?",
         "tier": "extracted", "signal": "transport volume", "is_data_question": True},
    ]},
}

GOOD_MODEL = {
    "anchor_date": "2026-03-01",
    "tables": [
        {"name": "pregnancies", "source_system": "Clinical EHR", "grain": "one episode",
         "primary_key": "episode_id", "primary_persona": "maria",
         "columns": [{"name": "episode_id", "type": "TEXT"}, {"name": "patient_id", "type": "TEXT"}]},
    ],
    "relationships": [],
    "messiness_profile": {"tables_without_pk": []},
}
# "pregnancy" nearly matches the source table "pregnancies": the audit must loop back
NEAR_MISS_MODEL = {
    **GOOD_MODEL,
    "tables": [{**GOOD_MODEL["tables"][0], "name": "pregnancy"}],
}

SCENARIO = {
    "scenarios": [
        {"id": "SC-1", "event_id": None, "description": "Shape the committed count.",
         "statements": [{"purpose": "mark actives",
                         "sql": "UPDATE pregnancies SET patient_id = patient_id WHERE episode_id = 'E1'"}],
         "checks": [{"figure": "overdue", "sql": "SELECT count(*) FROM pregnancies",
                     "expected": 38, "tolerance_abs": 0}]}
    ]
}


def ontology_slice(persona_id: str, name: str) -> dict:
    return {
        "nodes": [
            {"id": f"C-{persona_id}", "kind": "Concept", "name": "Pregnancy Episode",
             "definition": "One pregnancy followed from confirmation to outcome.",
             "synonyms": ["pregnancy", persona_id], "status": "active"},
            {"id": f"P-{persona_id}", "kind": "Persona", "persona_id": persona_id, "name": name},
        ],
        "edges": [
            {"id": f"S-{persona_id}", "type": "SERVES", "from": f"P-{persona_id}", "to": f"C-{persona_id}"},
            {"id": f"M-{persona_id}", "type": "MAPS_TO", "from": f"C-{persona_id}", "to": "E-pregnancies"},
        ],
        "duplicate_candidates": [],
        "coverage_gaps_detected": [],
    }


def finish(result, confidence=0.9):
    return {"action": "finish", "result": result, "confidence": confidence}


class ScriptedGateway:
    """Routes each call by prompt content; counts calls per stage; can be told to crash once."""

    def __init__(self, *, near_miss_first: bool = False, crash_at_scenario: bool = False):
        self.stage_calls: dict[str, int] = {}
        self.entity_tasks: list[str] = []
        self.near_miss_first = near_miss_first
        self.crash_at_scenario = crash_at_scenario

    def _bump(self, stage: str) -> int:
        self.stage_calls[stage] = self.stage_calls.get(stage, 0) + 1
        return self.stage_calls[stage]

    @staticmethod
    def _focus_persona(text: str, marker: str) -> str:
        # the first "id:" line after the focus marker is the item persona; the IR dump that
        # follows names every persona, so distance decides
        after = text[text.find(marker):]
        positions = [
            (position, persona)
            for persona in ("maria", "james")
            if (position := after.find(f"id: {persona}\n")) != -1
        ]
        return min(positions)[1]

    def complete(self, messages, purpose, ctx, response_schema=None):
        ctx["usage"].add(100, 50)
        text = "\n".join(m.content for m in messages)
        if "Curate ONLY this persona's slice" in text:
            persona = self._focus_persona(text, "Curate ONLY this persona's slice")
            self._bump(f"ontology:{persona}")
            name = "Maria" if persona == "maria" else "James"
            content = finish(ontology_slice(persona, name))
        elif "Design questions ONLY for this persona" in text:
            persona = self._focus_persona(text, "Design questions ONLY for this persona")
            self._bump(f"questions:{persona}")
            content = finish(QUESTIONS[persona])
        elif "SYNTHETIC database state" in text:
            calls = self._bump("scenario")
            if self.crash_at_scenario and calls == 1:
                raise KeyboardInterrupt("simulated kill mid-run")
            content = finish(SCENARIO)
        elif "Current PostgreSQL catalog headers" in text:
            calls = self._bump("entities")
            self.entity_tasks.append(text)
            content = finish(NEAR_MISS_MODEL if self.near_miss_first and calls == 1 else GOOD_MODEL)
        elif "PRD file:" in text:
            self._bump("requirements")
            content = finish(IR)
        else:
            raise AssertionError("unrecognized stage prompt")
        return CompletionResult(
            content=content, usage=Usage(prompt_tokens=100, completion_tokens=50), model="fake"
        )


class FakeDesign:
    def __init__(self, gateway):
        self.gateway = gateway
        self.app = load_app_profile(ROOT / "apps" / "rain" / "app.yaml")
        self.principal = Principal(
            subject="svc-prd-test", tenant="svc-internal", roles=(), entitlement_digest="0" * 64
        )
        self.meter = TokenMeter()
        self.run_token_budget = 600_000

    def usage_report(self):
        usage = self.meter.total()
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total": usage.total,
            "run_token_budget": self.run_token_budget,
        }


def make_workspace(root: Path):
    input_path = root / "prd.md"
    input_path.write_text(PRD_TEXT, encoding="utf-8")
    csv_dir = root / "csv"
    csv_dir.mkdir()
    with (csv_dir / "pregnancies.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(["episode_id", "patient_id"])
    return input_path, csv_dir, root / "out"


class PrdGraphRunTests(unittest.TestCase):
    def run_graph(self, gateway, output_dir, input_path, csv_dir, **kwargs):
        runner = PrdRunner({}, design=FakeDesign(gateway))
        return runner, runner.run(
            input_path, output_dir, csv_dir=csv_dir,
            catalog_path=output_dir / "missing-snapshot.json", **kwargs,
        )

    def test_full_run_with_per_persona_fanout(self):
        with tempfile.TemporaryDirectory() as temp:
            input_path, csv_dir, out = make_workspace(Path(temp))
            gateway = ScriptedGateway()
            _, report = self.run_graph(gateway, out, input_path, csv_dir)

            self.assertTrue(report["completed"], report)
            self.assertEqual(gateway.stage_calls["questions:maria"], 1)
            self.assertEqual(gateway.stage_calls["questions:james"], 1)
            self.assertEqual(gateway.stage_calls["ontology:maria"], 1)
            self.assertEqual(gateway.stage_calls["ontology:james"], 1)
            registry = yaml.safe_load((out / "question-registry.yaml").read_text(encoding="utf-8"))
            owners = {q["persona_id"] for q in registry["questions"]}
            self.assertEqual(owners, {"maria", "james"})
            upper = json.loads((out / "upper-ontology.json").read_text(encoding="utf-8"))
            concepts = [n for n in upper["nodes"] if n["kind"] == "Concept"]
            self.assertEqual(len(concepts), 1)  # the two persona slices merged one concept
            self.assertIn("james", concepts[0]["synonyms"])  # synonyms were unioned
            self.assertEqual(len(upper["duplicate_candidates"]), 1)
            audit = json.loads((out / "ontology-audit.json").read_text(encoding="utf-8"))
            self.assertEqual(audit["persona_nodes"], 2)
            self.assertEqual(audit["invalid_edge_references"], [])
            scenario = yaml.safe_load((out / "scenario.yaml").read_text(encoding="utf-8"))
            self.assertTrue(scenario["synthetic"])
            events = [
                json.loads(line)
                for line in (out / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(events[0]["type"], "graph_definition")
            self.assertEqual(events[0]["agent_name"], "data-orchestrator")
            self.assertIn("question_design", events[0]["steps"])
            picked = [e for e in events if e["type"] == "supervisor_decision"]
            self.assertTrue(picked, "no supervisor decisions were emitted")
            self.assertTrue(all(e["reason"] and e["skill"] for e in picked))
            branches = {e.get("branch") for e in events
                        if e["type"] == "stage_finished" and e["step_id"] == "question_design"}
            self.assertEqual(branches, {"maria", "james"})
            self.assertEqual(events[-1]["type"], "run_finished")
            self.assertEqual(events[-1]["outcome"], "completed")
            # a finished run's checkpoint holds PRD content and must be gone
            self.assertEqual(list((out / "checkpoints").glob("*.sqlite")), [])

    def test_schema_audit_mismatch_loops_back_to_the_entity_designer(self):
        with tempfile.TemporaryDirectory() as temp:
            input_path, csv_dir, out = make_workspace(Path(temp))
            gateway = ScriptedGateway(near_miss_first=True)
            _, report = self.run_graph(gateway, out, input_path, csv_dir)

            self.assertTrue(report["completed"], report)
            self.assertEqual(gateway.stage_calls["entities"], 2)  # the audit sent it back once
            self.assertIn("nearly matches source table", gateway.entity_tasks[1])
            model = yaml.safe_load((out / "entity-model.yaml").read_text(encoding="utf-8"))
            self.assertEqual(model["tables"][0]["name"], "pregnancies")  # the fixed model won
            self.assertEqual(report["stages"]["entity_modeling"]["runs"], 2)

    def test_killed_run_resumes_from_its_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            input_path, csv_dir, out = make_workspace(Path(temp))
            gateway = ScriptedGateway(crash_at_scenario=True)
            run_id = "resumetest0000000000000000000001"
            with self.assertRaises(KeyboardInterrupt):
                self.run_graph(gateway, out, input_path, csv_dir, run_id=run_id)
            self.assertTrue((out / "checkpoints" / f"{run_id}.sqlite").is_file())

            gateway.crash_at_scenario = False
            _, report = self.run_graph(
                gateway, out, input_path, csv_dir, run_id=run_id, resume=True
            )
            self.assertTrue(report["completed"], report)
            # the stages before the crash were not re-run on resume
            self.assertEqual(gateway.stage_calls["requirements"], 1)
            self.assertEqual(gateway.stage_calls["questions:maria"], 1)
            self.assertEqual(gateway.stage_calls["entities"], 1)
            self.assertEqual(gateway.stage_calls["scenario"], 2)  # crashed once, succeeded once
            self.assertTrue((out / "upper-ontology.json").is_file())


if __name__ == "__main__":
    unittest.main()
