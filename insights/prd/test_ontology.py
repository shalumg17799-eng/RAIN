import json
import unittest

from insights.prd.ontology import (
    build_ontology_tools,
    compact_lower,
    upper_ontology_curator_agent,
    upper_ontology_errors,
)

IR = {"personas": [{"id": "maria", "name": "Maria"}]}
REGISTRY = {"questions": [{"persona_id": "maria", "text": "How many?", "tier": "extracted"}]}
LOWER = {
    "nodes": [
        {"id": "E-pregnancies", "kind": "Entity", "name": "pregnancies"},
        {"id": "A-pregnancies-episodeid", "kind": "Attribute", "name": "episode_id"},
    ],
    "edges": [
        {"id": "H1", "type": "HAS_ATTRIBUTE", "from": "E-pregnancies", "to": "A-pregnancies-episodeid"},
    ],
}


def valid_upper():
    return {
        "nodes": [
            {"id": "C-0001", "kind": "Concept", "name": "Pregnancy Episode",
             "definition": "One pregnancy followed from confirmation to outcome.",
             "synonyms": ["pregnancy", "episode"], "status": "active"},
            {"id": "P-MARIA", "kind": "Persona", "persona_id": "maria", "name": "Maria"},
        ],
        "edges": [
            {"id": "S1", "type": "SERVES", "from": "P-MARIA", "to": "C-0001"},
            {"id": "M1", "type": "MAPS_TO", "from": "C-0001", "to": "E-pregnancies"},
        ],
        "duplicate_candidates": [],
        "coverage_gaps_detected": [],
    }


class UpperOntologyValidatorTests(unittest.TestCase):
    def test_valid_upper_passes(self):
        self.assertEqual(upper_ontology_errors(valid_upper(), IR, LOWER, None), [])

    def test_edge_to_unknown_id_is_an_error(self):
        draft = valid_upper()
        draft["edges"][1]["to"] = "E-ghosts"
        errors = upper_ontology_errors(draft, IR, LOWER, None)
        self.assertTrue(any("unknown node" in e for e in errors))

    def test_wrong_edge_kind_is_an_error(self):
        draft = valid_upper()
        draft["edges"][0]["type"] = "MAPS_TO"  # Persona -> Concept is not a MAPS_TO
        errors = upper_ontology_errors(draft, IR, LOWER, None)
        self.assertTrue(any("wrong node" in e for e in errors))

    def test_missing_persona_node_is_an_error(self):
        draft = valid_upper()
        draft["nodes"] = [n for n in draft["nodes"] if n["kind"] != "Persona"]
        draft["edges"] = [e for e in draft["edges"] if e["type"] != "SERVES"]
        errors = upper_ontology_errors(draft, IR, LOWER, None)
        self.assertTrue(any("no Persona node" in e for e in errors))

    def test_concept_without_definition_or_synonyms_is_an_error(self):
        draft = valid_upper()
        del draft["nodes"][0]["definition"]
        del draft["nodes"][0]["synonyms"]
        errors = upper_ontology_errors(draft, IR, LOWER, None)
        self.assertTrue(any("no definition" in e for e in errors))
        self.assertTrue(any("no synonyms" in e for e in errors))

    def test_dropping_an_existing_concept_id_is_an_error(self):
        existing = valid_upper()
        draft = valid_upper()
        draft["nodes"][0]["id"] = "C-9999"
        draft["edges"] = [
            {"id": "S1", "type": "SERVES", "from": "P-MARIA", "to": "C-9999"},
            {"id": "M1", "type": "MAPS_TO", "from": "C-9999", "to": "E-pregnancies"},
        ]
        errors = upper_ontology_errors(draft, IR, LOWER, existing)
        self.assertTrue(any("reconciled, never regenerated" in e for e in errors))


class OntologyToolTests(unittest.TestCase):
    def test_compact_lower_lists_every_mappable_id(self):
        compact = compact_lower(LOWER)
        self.assertEqual(compact["entities"][0]["id"], "E-pregnancies")
        self.assertEqual(compact["entities"][0]["attributes"], ["A-pregnancies-episodeid"])

    def test_read_lower_filters_by_kind_and_name(self):
        tools = build_ontology_tools(IR, LOWER, None)
        payload = json.loads(
            tools.invoke("read_lower_ontology", {"kind": "Attribute", "name_contains": "episode"}).text
        )
        self.assertEqual(payload["node_count"], 1)

    def test_read_existing_reports_first_run(self):
        tools = build_ontology_tools(IR, LOWER, None)
        payload = json.loads(tools.invoke("read_existing_upper_ontology", {}).text)
        self.assertFalse(payload["exists"])

    def test_audit_tool_runs_the_real_audit(self):
        tools = build_ontology_tools(IR, LOWER, None)
        payload = json.loads(tools.invoke("run_ontology_audit", {"draft": valid_upper()}).text)
        self.assertEqual(payload["concept_nodes"], 1)
        self.assertEqual(payload["invalid_edge_references"], [])


class OntologyAgentTests(unittest.TestCase):
    def test_invalid_edge_is_repaired_on_the_second_iteration(self):
        from insights.runtime.test_skill_agent import FakeGateway, make_ctx

        broken = valid_upper()
        broken["edges"][1]["to"] = "E-ghosts"
        gateway = FakeGateway([
            {"action": "finish", "result": broken, "confidence": 0.9},
            {"action": "finish", "result": valid_upper(), "confidence": 0.9},
        ])
        ctx, _ = make_ctx(gateway)
        agent = upper_ontology_curator_agent()
        self.assertEqual(agent.spec.capabilities.stage, "ontology")
        out = agent.run(
            {"requirements_ir": IR, "question_registry": REGISTRY, "lower_ontology": LOWER},
            ctx,
        )
        self.assertEqual(out["label"], "ok")
        self.assertEqual(out["repairs"], 1)
        repair = gateway.calls[1]["messages"][-1].content
        self.assertIn("unknown node", repair)


if __name__ == "__main__":
    unittest.main()
