import unittest
from pathlib import Path

from insights.prd.datamap import build_lower_ontology, compare_schema, datamap_label
from insights.skills_core.registry import SkillRegistry

ROOT = Path(__file__).resolve().parents[2]

MODEL = {
    "tables": [
        {"name": "pregnancies", "primary_key": "episode_id",
         "columns": [{"name": "episode_id", "type": "TEXT"}, {"name": "patient_id", "type": "TEXT"}]},
    ],
    "relationships": [],
}


class DatamapLabelTests(unittest.TestCase):
    def test_clean_audit_is_ok(self):
        audit = compare_schema(MODEL, {"pregnancies": ["episode_id", "patient_id"]}, {})
        label, critique = datamap_label(audit)
        self.assertEqual(label, "ok")
        self.assertIsNone(critique)

    def test_near_miss_table_name_routes_back_with_a_critique(self):
        # the model says "pregnancy" while the source table is "pregnancies": a near miss
        model = {"tables": [{"name": "pregnancy", "columns": [{"name": "episode_id", "type": "TEXT"}]}], "relationships": []}
        audit = compare_schema(model, {"pregnancies": ["episode_id"]}, {})
        label, critique = datamap_label(audit)
        self.assertEqual(label, "refine_entity_model")
        self.assertIn("nearly matches source table", critique)

    def test_near_miss_column_name_routes_back(self):
        model = {"tables": [{"name": "pregnancies", "columns": [{"name": "episode_identifier", "type": "TEXT"}]}], "relationships": []}
        audit = compare_schema(model, {"pregnancies": ["episode_id"]}, {})
        label, critique = datamap_label(audit)
        self.assertEqual(label, "refine_entity_model")
        self.assertIn("episode_id", critique)

    def test_genuinely_new_table_stays_ok(self):
        model = {
            "tables": [
                {"name": "pregnancies", "columns": [{"name": "episode_id", "type": "TEXT"}]},
                {"name": "community_events", "columns": [{"name": "event_id", "type": "TEXT"}]},
            ],
            "relationships": [],
        }
        audit = compare_schema(model, {"pregnancies": ["episode_id"]}, {})
        label, _ = datamap_label(audit)
        self.assertEqual(label, "ok")
        self.assertIn("community_events", audit["tables_not_in_source"])


class BuildDataMapSkillTests(unittest.TestCase):
    def test_registry_loads_and_runs_the_skill_without_any_model(self):
        registry = SkillRegistry.scan(ROOT / "skills")
        self.assertIn("build-data-map", registry.names())
        notes = []
        ctx = {"emit": lambda note, count=None: notes.append((note, count))}
        out = registry.invoke(
            "build-data-map", None,
            {"entity_model": MODEL, "source_schema": {"pregnancies": ["episode_id", "patient_id"]},
             "catalog_schema": {}},
            ctx,
        )
        self.assertEqual(out["label"], "ok")
        self.assertEqual(len(out["lower_ontology"]["nodes"]), 3)  # 1 entity + 2 attributes
        self.assertEqual(out["schema_audit"]["entity_model_table_count"], 1)
        self.assertIn(("datamap_nodes", 3), notes)

    def test_lower_ontology_builds_reference_edges(self):
        model = {
            "tables": [
                {"name": "a", "columns": [{"name": "id", "type": "TEXT"}]},
                {"name": "b", "columns": [{"name": "a_id", "type": "TEXT"}]},
            ],
            "relationships": [{"from_table": "b", "to_table": "a", "from_column": "a_id", "to_column": "id"}],
        }
        lower = build_lower_ontology(model)
        self.assertTrue(any(edge["type"] == "REFERENCES" for edge in lower["edges"]))


if __name__ == "__main__":
    unittest.main()
