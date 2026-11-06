import json
import unittest

from insights.prd.questions import (
    build_question_tools,
    dedupe,
    persona_question_designer_agent,
    question_registry_errors,
)


def sample_ir():
    return {
        "mode": "persona_questions",
        "anchor_date": "2026-03-01",
        "personas": [
            {"id": "maria", "name": "Maria", "role": "Medical Director"},
            {"id": "james", "name": "James", "role": "EMS Coordinator"},
        ],
        "questions": [
            {"id": "Q1", "persona_id": "maria", "text": "How many pregnancies are active?",
             "tier": "extracted", "is_data_question": True},
        ],
        "committed_figures": [], "source_systems": [], "entity_hints": [],
        "narrative_events": [], "constraints": [], "open_items": [],
    }


def good_registry():
    return {
        "questions": [
            {"persona_id": "maria", "text": "How many pregnancies are active?",
             "tier": "extracted", "signal": "active pregnancies", "is_data_question": True},
            {"persona_id": "james", "text": "How many transports ran today?",
             "tier": "derived", "signal": "transport volume", "is_data_question": True},
        ]
    }


class QuestionValidatorTests(unittest.TestCase):
    def test_good_registry_passes(self):
        self.assertEqual(question_registry_errors(good_registry(), sample_ir()), [])

    def test_unknown_persona_is_an_error(self):
        draft = good_registry()
        draft["questions"][1]["persona_id"] = "ghost"
        errors = question_registry_errors(draft, sample_ir())
        self.assertTrue(any("ghost" in e for e in errors))

    def test_dropped_extracted_question_is_an_error(self):
        draft = good_registry()
        draft["questions"] = draft["questions"][1:]  # the extracted Q1 is gone
        errors = question_registry_errors(draft, sample_ir())
        self.assertTrue(any("must be preserved" in e for e in errors))

    def test_duplicates_are_an_error(self):
        draft = good_registry()
        draft["questions"].append(dict(draft["questions"][0]))
        errors = question_registry_errors(draft, sample_ir())
        self.assertTrue(any("duplicate question" in e for e in errors))

    def test_bad_tier_is_an_error(self):
        draft = good_registry()
        draft["questions"][0]["tier"] = "invented"
        errors = question_registry_errors(draft, sample_ir())
        self.assertTrue(any("tier must be one of" in e for e in errors))

    def test_dedupe_keeps_first_and_reports_removed(self):
        items = good_registry()["questions"]
        unique, removed = dedupe([*items, dict(items[0])])
        self.assertEqual(len(unique), 2)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["persona_id"], "maria")


class QuestionToolTests(unittest.TestCase):
    def test_get_persona_and_unknown_persona(self):
        tools = build_question_tools(sample_ir())
        ok = tools.invoke("get_persona", {"id": "james"})
        self.assertTrue(ok.ok)
        self.assertIn("EMS Coordinator", ok.text)
        bad = tools.invoke("get_persona", {"id": "ghost"})
        self.assertFalse(bad.ok)
        self.assertIn("maria", bad.text)

    def test_read_ir_section(self):
        tools = build_question_tools(sample_ir())
        outcome = tools.invoke("read_requirements_ir", {"section": "personas"})
        payload = json.loads(outcome.text)
        self.assertEqual(len(payload["personas"]), 2)

    def test_dedupe_tool(self):
        tools = build_question_tools(sample_ir())
        items = good_registry()["questions"]
        outcome = tools.invoke("dedupe_questions", {"questions": [*items, dict(items[0])]})
        payload = json.loads(outcome.text)
        self.assertEqual(payload["unique_count"], 2)
        self.assertEqual(len(payload["removed_duplicates"]), 1)


class QuestionAgentTests(unittest.TestCase):
    def test_dropped_extracted_question_is_repaired_on_the_second_iteration(self):
        from insights.runtime.test_skill_agent import FakeGateway, make_ctx

        incomplete = good_registry()
        incomplete["questions"] = incomplete["questions"][1:]
        gateway = FakeGateway([
            {"action": "finish", "result": incomplete, "confidence": 0.9},
            {"action": "finish", "result": good_registry(), "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        agent = persona_question_designer_agent()
        self.assertEqual(agent.spec.capabilities.stage, "questions")
        out = agent.run({"requirements_ir": sample_ir()}, ctx)
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["repairs"], 1)
        self.assertEqual(out["iterations"], 2)
        repair = gateway.calls[1]["messages"][-1].content
        self.assertIn("must be preserved", repair)


if __name__ == "__main__":
    unittest.main()
