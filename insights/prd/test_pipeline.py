import csv
import json
import tempfile
import time
import unittest
from pathlib import Path

import yaml

from insights.contracts.gateway import CompletionResult, Usage
from insights.prd.pipeline import PrdPipeline
from insights.runtime.stores import MonotonicDeadline, TokenMeter


class FakeModel:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def complete(self, system, prompt, *, max_tokens, response_schema=None):
        self.calls.append((system, prompt, max_tokens, response_schema))
        return next(self.outputs)


class FakeDesignGateway:
    """Replays scripted action envelopes for the stage-1 skill agent."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def complete(self, messages, purpose, ctx, response_schema=None):
        self.calls.append({"messages": tuple(messages), "purpose": purpose})
        ctx["usage"].add(100, 50)
        return CompletionResult(
            content=self.outputs.pop(0),
            usage=Usage(prompt_tokens=100, completion_tokens=50),
            model="fake-model",
        )


class FakeDesignRuntime:
    def __init__(self, gateway):
        self.gateway = gateway
        self.meter = TokenMeter()
        self.run_token_budget = 600_000

    def check_run_budget(self, stage):
        total = self.meter.total().total
        if total >= self.run_token_budget:
            raise ValueError(f"budget exhausted before {stage}")

    def usage_report(self):
        usage = self.meter.total()
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total": usage.total,
            "run_token_budget": self.run_token_budget,
        }

    def context(self, *, step_id, timeout_ms):
        return {
            "run_id": "r1",
            "trace_id": "a" * 32,
            "step_id": step_id,
            "attempt": 0,
            "usage": self.meter,
            "deadline": MonotonicDeadline(time.monotonic, timeout_ms),
            "emit": lambda note, count=None: None,
            "gateway": self.gateway,
        }


class PrdPipelineTests(unittest.TestCase):
    def test_malformed_stage_output_gets_one_format_only_repair(self):
        model = FakeModel(["not valid yaml: [", '{"personas": [], "questions": []}'])
        pipeline = PrdPipeline(model)
        pipeline._current_input = "input for fake stage"

        result = pipeline._run_parsed_skill(
            "requirements-interpreter",
            "Return structured output.",
            shape="an object with personas and questions",
        )

        self.assertEqual(result["personas"], [])
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(model.calls[0][3]["type"], "object")

    def test_runs_prd_chain_and_audits_schema_and_ontology(self):
        requirements = {
            "mode": "persona_questions",
            "domain": "rural health",
            "anchor_date": "2026-03-01",
            "personas": [{"id": "maria", "name": "Maria", "role": "Medical Director", "altitude": "executive", "problems": ["maternal access"], "systems": ["Clinical EHR"]}],
            "questions": [{"id": "Q1", "persona_id": "maria", "text": "How many pregnancies are active?", "tier": "extracted", "is_data_question": True}],
            "committed_figures": [],
            "source_systems": ["Clinical EHR"],
            "entity_hints": ["PregnancyEpisode"],
            "narrative_events": [],
            "constraints": [],
            "open_items": [],
        }
        questions = [{"persona_id": "maria", "text": "How many pregnancies are active?", "tier": "extracted", "signal": "active pregnancy count", "is_data_question": True}]
        entity_model = {
            "anchor_date": "2026-03-01",
            "tables": [{"name": "pregnancies", "source_system": "Clinical EHR", "grain": "one pregnancy episode", "primary_key": "episode_id", "primary_persona": "maria", "columns": [{"name": "episode_id", "type": "TEXT"}, {"name": "patient_id", "type": "TEXT"}]}],
            "relationships": [],
            "messiness_profile": {"tables_without_pk": []},
        }
        upper = {
            "nodes": [
                {"id": "C-EPISODE", "kind": "Concept", "name": "Episode", "synonyms": ["pregnancy"], "status": "needs_review"},
                {"id": "P-MARIA", "kind": "Persona", "persona_id": "maria", "name": "Maria"},
            ],
            "edges": [
                {"id": "S1", "type": "SERVES", "from": "P-MARIA", "to": "C-EPISODE"},
                {"id": "M1", "type": "MAPS_TO", "from": "C-EPISODE", "to": "E-pregnancies"},
            ],
            "duplicate_candidates": [],
            "coverage_gaps_detected": [],
        }
        model = FakeModel([yaml.safe_dump(requirements), yaml.safe_dump(questions), yaml.safe_dump(entity_model), json.dumps(upper)])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "prd.md"
            input_path.write_text("Maria needs maternal access reporting.", encoding="utf-8")
            csv_dir = root / "csv"
            csv_dir.mkdir()
            with (csv_dir / "pregnancies.csv").open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerow(["episode_id", "patient_id", "expected_delivery_date"])
            output_dir = root / "out"

            report = PrdPipeline(model).run(input_path, output_dir, csv_dir=csv_dir, catalog_path=root / "missing-snapshot.json")

            self.assertEqual(len(model.calls), 4)
            for name in ("requirements-ir.yaml", "question-registry.yaml", "entity-model.yaml", "lower-ontology.json", "upper-ontology.json", "schema-audit.json", "scenario-status.yaml"):
                self.assertTrue((output_dir / name).is_file())
            self.assertEqual(report["ontology_audit"]["invalid_edge_references"], [])
            self.assertEqual(report["ontology_audit"]["personas_missing_from_ontology"], [])
            schema_audit = json.loads((output_dir / "schema-audit.json").read_text(encoding="utf-8"))
            table_audit = schema_audit["tables"][0]
            self.assertEqual(table_audit["source_columns_missing_from_entity_model"], ["expected_delivery_date"])
            self.assertEqual(table_audit["similar_column_candidates"], [])

    def test_stage_one_runs_through_the_skill_agent_when_a_design_runtime_is_given(self):
        requirements = {
            "mode": "persona_questions",
            "domain": "rural health",
            "anchor_date": "2026-03-01",
            "personas": [{"id": "maria", "name": "Maria", "role": "Medical Director", "altitude": "executive", "problems": ["maternal access"], "systems": ["Clinical EHR"]}],
            "questions": [{"id": "Q1", "persona_id": "maria", "text": "How many pregnancies are active?", "tier": "extracted", "is_data_question": True}],
            "committed_figures": [],
            "source_systems": ["Clinical EHR"],
            "entity_hints": ["PregnancyEpisode"],
            "narrative_events": [],
            "constraints": [],
            "open_items": [],
        }
        questions = [{"persona_id": "maria", "text": "How many pregnancies are active?", "tier": "extracted", "signal": "active pregnancy count", "is_data_question": True}]
        entity_model = {
            "anchor_date": "2026-03-01",
            "tables": [{"name": "pregnancies", "source_system": "Clinical EHR", "grain": "one pregnancy episode", "primary_key": "episode_id", "primary_persona": "maria", "columns": [{"name": "episode_id", "type": "TEXT"}]}],
            "relationships": [],
            "messiness_profile": {"tables_without_pk": []},
        }
        upper = {
            "nodes": [
                {"id": "C-EPISODE", "kind": "Concept", "name": "Episode", "synonyms": ["pregnancy"], "status": "needs_review"},
                {"id": "P-MARIA", "kind": "Persona", "persona_id": "maria", "name": "Maria"},
            ],
            "edges": [{"id": "S1", "type": "SERVES", "from": "P-MARIA", "to": "C-EPISODE"}],
            "duplicate_candidates": [],
            "coverage_gaps_detected": [],
        }
        gateway = FakeDesignGateway([
            {"action": "finish", "result": requirements, "confidence": 0.9},
            {"action": "finish", "result": {"questions": questions}, "confidence": 0.9},
        ])
        model = FakeModel([yaml.safe_dump(entity_model), json.dumps(upper)])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "prd.md"
            input_path.write_text("Maria needs maternal access reporting.", encoding="utf-8")
            output_dir = root / "out"

            pipeline = PrdPipeline(model, design_runtime=FakeDesignRuntime(gateway))
            report = pipeline.run(
                input_path, output_dir, csv_dir=root / "no-csv",
                catalog_path=root / "missing-snapshot.json",
            )

            self.assertEqual(len(gateway.calls), 2)  # stages 1 and 2 went through the gateway
            self.assertEqual(gateway.calls[0]["purpose"].value, "design")
            self.assertEqual(len(model.calls), 2)  # stages 3 and 5 stayed on the legacy path
            saved = yaml.safe_load((output_dir / "requirements-ir.yaml").read_text(encoding="utf-8"))
            self.assertEqual(saved["personas"][0]["id"], "maria")
            self.assertEqual(report["stages"][0], "requirements-interpreter")


if __name__ == "__main__":
    unittest.main()