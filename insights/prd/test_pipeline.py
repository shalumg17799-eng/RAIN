import csv
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from insights.prd.pipeline import PrdPipeline


class FakeModel:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def complete(self, system, prompt, *, max_tokens):
        self.calls.append((system, prompt, max_tokens))
        return next(self.outputs)


class PrdPipelineTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()