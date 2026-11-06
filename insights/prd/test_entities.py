import json
import unittest

from insights.prd.entities import (
    build_entity_tools,
    entity_model_designer_agent,
    entity_model_errors,
)

IR = {"anchor_date": "2026-03-01", "personas": [{"id": "maria"}]}
REGISTRY = {
    "questions": [
        {"persona_id": "maria", "text": "How many pregnancies are active?",
         "tier": "extracted", "is_data_question": True},
        {"persona_id": "maria", "text": "Show quasar luminosity by epoch",
         "tier": "derived", "is_data_question": True},
    ]
}
SOURCE = {"pregnancies": ["episode_id", "patient_id", "expected_delivery_date"]}
CATALOG = {"PregnancyEpisode": ["episode_id", "patient_id"]}


def valid_model():
    return {
        "anchor_date": "2026-03-01",
        "tables": [
            {
                "name": "pregnancies",
                "source_system": "Clinical EHR",
                "grain": "one pregnancy episode",
                "primary_key": "episode_id",
                "primary_persona": "maria",
                "columns": [
                    {"name": "episode_id", "type": "TEXT"},
                    {"name": "patient_id", "type": "TEXT"},
                    {"name": "is_active", "type": "BOOLEAN"},
                ],
            }
        ],
        "relationships": [],
        "messiness_profile": {"tables_without_pk": []},
    }


class EntityValidatorTests(unittest.TestCase):
    def test_valid_model_passes(self):
        self.assertEqual(entity_model_errors(valid_model(), IR), [])

    def test_missing_primary_key_is_an_error_unless_declared_messy(self):
        draft = valid_model()
        del draft["tables"][0]["primary_key"]
        errors = entity_model_errors(draft, IR)
        self.assertTrue(any("primary_key" in e for e in errors))
        draft["messiness_profile"]["tables_without_pk"] = ["pregnancies"]
        self.assertEqual(entity_model_errors(draft, IR), [])

    def test_relationship_to_unknown_table_is_an_error(self):
        draft = valid_model()
        draft["relationships"] = [{"from_table": "pregnancies", "to_table": "ghosts"}]
        errors = entity_model_errors(draft, IR)
        self.assertTrue(any("ghosts" in e for e in errors))

    def test_changed_anchor_date_is_an_error(self):
        draft = valid_model()
        draft["anchor_date"] = None
        errors = entity_model_errors(draft, IR)
        self.assertTrue(any("anchor_date must be copied verbatim" in e for e in errors))

    def test_column_without_type_is_an_error(self):
        draft = valid_model()
        draft["tables"][0]["columns"][0] = {"name": "episode_id"}
        errors = entity_model_errors(draft, IR)
        self.assertTrue(any("name and type" in e for e in errors))


class EntityToolTests(unittest.TestCase):
    def test_read_headers_whole_and_single(self):
        tools = build_entity_tools(SOURCE, CATALOG, REGISTRY)
        all_source = json.loads(tools.invoke("read_csv_headers", {}).text)
        self.assertEqual(all_source["tables"], ["pregnancies"])
        one = json.loads(tools.invoke("read_catalog_snapshot", {"table": "pregnancyepisode"}).text)
        self.assertIn("PregnancyEpisode", one)

    def test_schema_audit_runs_the_real_compare(self):
        tools = build_entity_tools(SOURCE, CATALOG, REGISTRY)
        outcome = tools.invoke("run_schema_audit", {"draft": valid_model()})
        payload = json.loads(outcome.text)
        self.assertEqual(payload["entity_model_table_count"], 1)
        self.assertIn(
            "expected_delivery_date",
            payload["tables"][0]["source_columns_missing_from_entity_model"],
        )

    def test_answerability_flags_questions_with_no_overlap(self):
        tools = build_entity_tools(SOURCE, CATALOG, REGISTRY)
        payload = json.loads(
            tools.invoke("check_question_answerability", {"draft": valid_model()}).text
        )
        flagged = payload["questions_with_no_overlap"]
        self.assertTrue(any("quasar" in q for q in flagged))
        self.assertFalse(any("pregnancies" in q for q in flagged))


class EntityAgentTests(unittest.TestCase):
    def test_anchor_date_drift_is_repaired_on_the_second_iteration(self):
        from insights.runtime.test_skill_agent import FakeGateway, make_ctx

        drifted = valid_model()
        drifted["anchor_date"] = "2026-06-01"
        gateway = FakeGateway([
            {"action": "finish", "result": drifted, "confidence": 0.9},
            {"action": "finish", "result": valid_model(), "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        agent = entity_model_designer_agent()
        self.assertEqual(agent.spec.capabilities.stage, "entities")
        out = agent.run(
            {"requirements_ir": IR, "question_registry": REGISTRY,
             "source_schema": SOURCE, "catalog_schema": CATALOG},
            ctx,
        )
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["repairs"], 1)
        repair = gateway.calls[1]["messages"][-1].content
        self.assertIn("anchor_date must be copied verbatim", repair)


if __name__ == "__main__":
    unittest.main()
