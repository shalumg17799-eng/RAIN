import unittest

from insights.prd.scenario import (
    generate_synthetic_db_state,
    scenario_designer_agent,
    scenario_errors,
)

IR = {"anchor_date": "2026-03-01", "personas": [{"id": "maria"}], "committed_figures": []}
MODEL = {
    "anchor_date": "2026-03-01",
    "tables": [
        {"name": "pregnancies", "grain": "one episode", "primary_key": "episode_id",
         "columns": [{"name": "episode_id", "type": "TEXT"}, {"name": "is_active", "type": "BOOLEAN"}]},
    ],
    "relationships": [],
}


def valid_scenarios():
    return {
        "scenarios": [
            {
                "id": "SC-1",
                "event_id": None,
                "description": "Make the active-pregnancy count hold.",
                "statements": [
                    {"purpose": "mark the committed episodes active",
                     "sql": "UPDATE pregnancies SET is_active = true WHERE episode_id = 'E-001'"},
                ],
                "checks": [
                    {"figure": "active_pregnancies", "question": "Q1",
                     "sql": "SELECT count(*) FROM pregnancies WHERE is_active",
                     "expected": 1, "tolerance_abs": 0},
                ],
            }
        ]
    }


class SyntheticStateTests(unittest.TestCase):
    def test_state_is_deterministic_synthetic_and_model_derived(self):
        first = generate_synthetic_db_state(MODEL)
        second = generate_synthetic_db_state(MODEL)
        self.assertEqual(first, second)
        self.assertTrue(first["synthetic"])
        self.assertEqual(first["source"], "generated_from_entity_model")
        self.assertEqual(first["anchor_date"], "2026-03-01")
        self.assertIn("pregnancies", first["tables"])
        self.assertGreaterEqual(first["tables"]["pregnancies"]["row_count"], 200)


class ScenarioValidatorTests(unittest.TestCase):
    def test_valid_scenarios_pass(self):
        self.assertEqual(scenario_errors(valid_scenarios(), MODEL), [])

    def test_select_statement_is_rejected(self):
        draft = valid_scenarios()
        draft["scenarios"][0]["statements"][0]["sql"] = "SELECT * FROM pregnancies"
        errors = scenario_errors(draft, MODEL)
        self.assertTrue(any("statements may only be" in e for e in errors))

    def test_now_is_rejected(self):
        draft = valid_scenarios()
        draft["scenarios"][0]["statements"][0]["sql"] = (
            "UPDATE pregnancies SET is_active = true WHERE created_at > now()"
        )
        errors = scenario_errors(draft, MODEL)
        self.assertTrue(any("never now()" in e for e in errors))

    def test_unknown_table_is_rejected(self):
        draft = valid_scenarios()
        draft["scenarios"][0]["statements"][0]["sql"] = "UPDATE ghosts SET x = 1"
        errors = scenario_errors(draft, MODEL)
        self.assertTrue(any("'ghosts' is not in the entity model" in e for e in errors))

    def test_check_must_be_select(self):
        draft = valid_scenarios()
        draft["scenarios"][0]["checks"][0]["sql"] = "DELETE FROM pregnancies"
        errors = scenario_errors(draft, MODEL)
        self.assertTrue(any("read-only SELECT" in e for e in errors))

    def test_destructive_alter_is_rejected(self):
        draft = valid_scenarios()
        draft["scenarios"][0]["statements"][0]["sql"] = "ALTER TABLE pregnancies DROP COLUMN is_active"
        errors = scenario_errors(draft, MODEL)
        self.assertTrue(any("ADD COLUMN IF NOT EXISTS" in e for e in errors))


class ScenarioAgentTests(unittest.TestCase):
    def test_relative_now_is_repaired_on_the_second_iteration(self):
        from insights.runtime.test_skill_agent import FakeGateway, make_ctx

        bad = valid_scenarios()
        bad["scenarios"][0]["statements"][0]["sql"] = (
            "UPDATE pregnancies SET is_active = true WHERE created_at > current_date"
        )
        gateway = FakeGateway([
            {"action": "finish", "result": bad, "confidence": 0.9},
            {"action": "finish", "result": valid_scenarios(), "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        agent = scenario_designer_agent()
        self.assertEqual(agent.spec.capabilities.stage, "scenario")
        out = agent.run(
            {"requirements_ir": IR, "entity_model": MODEL,
             "db_state": generate_synthetic_db_state(MODEL)},
            ctx,
        )
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["repairs"], 1)
        repair = gateway.calls[1]["messages"][-1].content
        self.assertIn("never now()", repair)


if __name__ == "__main__":
    unittest.main()
