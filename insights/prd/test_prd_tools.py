import json
import os
import tempfile
import unittest
from pathlib import Path

from insights.prd.tools import (
    PrdDocument,
    build_requirements_tools,
    document_sections,
    requirements_ir_errors,
)

DOC_TEXT = """RAIN Prototype Spec

Overview
The platform serves rural health. This morning the clinic saw a spike in calls.
Dr. Maria Delgado-Reyes oversees 38 pregnant patients across 5 counties.

Metrics
Transport requests rose to 1,204 last month.
"""

DOC = PrdDocument(name="spec.md", text=DOC_TEXT, sha256="0" * 64)


def valid_ir():
    return {
        "mode": "persona_questions",
        "domain": "rural health",
        "anchor_date": "2026-03-01",
        "personas": [{"id": "maria", "name": "Maria", "role": "Medical Director"}],
        "questions": [
            {"id": "Q1", "persona_id": "maria", "text": "How many?", "tier": "extracted",
             "is_data_question": True}
        ],
        "committed_figures": [{"id": "F1", "value": "38", "tolerance": "exact"}],
        "source_systems": [],
        "entity_hints": [],
        "narrative_events": [],
        "constraints": [],
        "open_items": [],
    }


class DocumentToolTests(unittest.TestCase):
    def test_sections_are_detected(self):
        sections = document_sections(DOC_TEXT)
        titles = [s["title"] for s in sections]
        self.assertIn("Overview", titles)
        self.assertIn("Metrics", titles)

    def test_search_finds_figures_with_context(self):
        tools = build_requirements_tools(DOC)
        outcome = tools.invoke("search_document", {"query": "38 pregnant"})
        self.assertTrue(outcome.ok)
        payload = json.loads(outcome.text)
        self.assertEqual(payload["match_count"], 1)
        self.assertIn("Delgado-Reyes", payload["matches"][0]["snippet"])

    def test_relative_time_is_detected(self):
        tools = build_requirements_tools(DOC)
        outcome = tools.invoke("check_relative_time_language", {})
        payload = json.loads(outcome.text)
        self.assertTrue(payload["has_relative_time"])
        self.assertIn("this morning", payload["examples"])

    def test_validate_tool_matches_the_finish_validator(self):
        tools = build_requirements_tools(DOC)
        draft = valid_ir()
        draft["anchor_date"] = None
        outcome = tools.invoke("validate_requirements_ir", {"draft": draft})
        payload = json.loads(outcome.text)
        self.assertFalse(payload["valid"])
        self.assertTrue(any("anchor_date" in e for e in payload["errors"]))

    def test_tools_write_nothing(self):
        """Every tool is read-only: invoking all of them creates no files anywhere nearby."""
        tools = build_requirements_tools(DOC)
        calls = [
            ("list_document_sections", {}),
            ("read_document_section", {"index": 0}),
            ("search_document", {"query": "clinic"}),
            ("check_relative_time_language", {}),
            ("validate_requirements_ir", {"draft": valid_ir()}),
        ]
        before = os.getcwd()
        with tempfile.TemporaryDirectory() as temp:
            os.chdir(temp)
            try:
                for name, args in calls:
                    self.assertTrue(tools.invoke(name, args).ok, name)
                self.assertEqual(os.listdir(temp), [])
            finally:
                os.chdir(before)


class RequirementsIrValidatorTests(unittest.TestCase):
    def test_valid_ir_has_no_errors(self):
        self.assertEqual(requirements_ir_errors(valid_ir(), DOC), [])

    def test_null_anchor_date_with_relative_time_is_an_error(self):
        draft = valid_ir()
        draft["anchor_date"] = None
        errors = requirements_ir_errors(draft, DOC)
        self.assertTrue(any("anchor_date" in e and "this morning" in e for e in errors))

    def test_question_with_unknown_persona_is_an_error(self):
        draft = valid_ir()
        draft["questions"][0]["persona_id"] = "ghost"
        errors = requirements_ir_errors(draft, DOC)
        self.assertTrue(any("ghost" in e for e in errors))

    def test_non_data_question_needs_a_reason(self):
        draft = valid_ir()
        draft["questions"][0]["is_data_question"] = False
        errors = requirements_ir_errors(draft, DOC)
        self.assertTrue(any("needs a reason" in e for e in errors))

    def test_committed_figure_must_appear_in_the_document(self):
        draft = valid_ir()
        draft["committed_figures"].append({"id": "F2", "value": "9,999"})
        errors = requirements_ir_errors(draft, DOC)
        self.assertTrue(any("9,999" in e for e in errors))

    def test_committed_figure_matches_despite_comma_formatting(self):
        draft = valid_ir()
        draft["committed_figures"].append({"id": "F2", "value": "1204"})
        self.assertEqual(requirements_ir_errors(draft, DOC), [])

    def test_missing_personas_is_an_error(self):
        draft = valid_ir()
        draft["personas"] = []
        errors = requirements_ir_errors(draft, DOC)
        self.assertTrue(any("at least one persona" in e for e in errors))


class ForcedRepairThroughTheRealAgentTests(unittest.TestCase):
    """Pilot evidence: a forced null anchor_date (with relative time in the document) triggers
    semantic repair and succeeds on the second iteration, through the REAL agent, spec, prompt
    and validators -- only the model is scripted."""

    def test_null_anchor_date_is_repaired_on_the_second_iteration(self):
        from insights.prd.tools import requirements_interpreter_agent
        from insights.runtime.test_skill_agent import FakeGateway, make_ctx

        bad = valid_ir()
        bad["anchor_date"] = None
        gateway = FakeGateway([
            {"action": "finish", "result": bad, "confidence": 0.9},
            {"action": "finish", "result": valid_ir(), "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        agent = requirements_interpreter_agent()
        self.assertEqual(agent.spec.capabilities.stage, "requirements")
        out = agent.run({"document": DOC_TEXT, "document_name": "spec.md"}, ctx)
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["iterations"], 2)
        self.assertEqual(out["repairs"], 1)
        repair = gateway.calls[1]["messages"][-1].content
        self.assertIn("anchor_date", repair)
        self.assertIn("this morning", repair)


if __name__ == "__main__":
    unittest.main()
