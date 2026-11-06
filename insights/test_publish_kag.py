"""Publishing the PRD ontology into the KAG: the transform, the audit gate, and retrieval."""

import unittest
from pathlib import Path

from insights.catalog.kag_neo4j import ColumnRow, ConceptRow, JoinRow, Neo4jKag
from insights.contracts.principal import Principal
from insights.contracts.profile import load_app_profile
from insights.prd.publish_kag import PublishRefused, assert_audit_clean, build_graph_rows

ROOT = Path(__file__).resolve().parents[1]
APP = load_app_profile(ROOT / "apps" / "rain" / "app.yaml")

UPPER = {
    "nodes": [
        {"id": "C-1", "kind": "Concept", "name": "PregnantPatient",
         "definition": "A patient in an active pregnancy episode.",
         "synonyms": ["pregnant patient", "maternity patient"]},
        {"id": "P-1", "kind": "Persona", "persona_id": "P1",
         "name": "Dr. Maria Delgado-Reyes", "role": "Medical Director"},
    ],
    "edges": [
        {"id": "MT-1", "type": "MAPS_TO", "from": "C-1", "to": "E-patient"},
        {"id": "SV-1", "type": "SERVES", "from": "P-1", "to": "C-1"},
    ],
}
LOWER = {
    "nodes": [
        {"id": "E-patient", "kind": "Entity", "name": "Patient",
         "grain": "one row per patient", "primary_key": "patient_id"},
        {"id": "E-episode", "kind": "Entity", "name": "PregnancyEpisode",
         "grain": "one episode", "primary_key": "episode_id"},
        {"id": "A-p-id", "kind": "Attribute", "name": "patient_id", "data_type": "uuid"},
        {"id": "A-p-county", "kind": "Attribute", "name": "county", "data_type": "text"},
        {"id": "A-e-pid", "kind": "Attribute", "name": "patient_id", "data_type": "uuid"},
    ],
    "edges": [
        {"id": "H1", "type": "HAS_ATTRIBUTE", "from": "E-patient", "to": "A-p-id"},
        {"id": "H2", "type": "HAS_ATTRIBUTE", "from": "E-patient", "to": "A-p-county"},
        {"id": "H3", "type": "HAS_ATTRIBUTE", "from": "E-episode", "to": "A-e-pid"},
        {"id": "R1", "type": "REFERENCES", "from": "E-episode", "to": "E-patient",
         "from_column": "patient_id", "to_column": "patient_id"},
    ],
}


class TransformTests(unittest.TestCase):
    def test_artifacts_become_the_retrieval_shape(self):
        rows = build_graph_rows(UPPER, LOWER)
        self.assertEqual({e["table"] for e in rows.entities}, {"Patient", "PregnancyEpisode"})
        pk = next(a for a in rows.attributes if a["table"] == "Patient" and a["name"] == "patient_id")
        self.assertTrue(pk["is_primary_key"])
        county = next(a for a in rows.attributes if a["name"] == "county")
        self.assertFalse(county["is_primary_key"])
        self.assertEqual(rows.references, [{
            "from_table": "PregnancyEpisode", "to_table": "Patient",
            "from_column": "patient_id", "to_column": "patient_id",
        }])
        self.assertEqual(rows.maps_to, [{"concept": "PregnantPatient", "table": "Patient"}])
        self.assertEqual(rows.serves,
                         [{"persona": "Dr. Maria Delgado-Reyes", "concept": "PregnantPatient"}])

    def test_audit_gate_refuses_flagged_runs(self):
        assert_audit_clean({"unmapped_concepts": [], "invalid_edge_references": []})
        with self.assertRaises(PublishRefused):
            assert_audit_clean({"unmapped_concepts": ["Orphan"], "invalid_edge_references": []})
        with self.assertRaises(PublishRefused):
            assert_audit_clean({"invalid_edge_references": ["E-ghost"]})


class FakeReader:
    """An in-memory graph in the published shape: CamelCase tables, like the real catalog."""

    def __init__(self):
        self._concepts = [ConceptRow(
            name="PregnantPatient",
            synonyms=("pregnant patient", "maternity patient"),
            definition="A patient in an active pregnancy episode.",
            tables=("Patient", "PregnancyEpisode"),
        )]
        self._columns = [
            ColumnRow("Patient", "patient_id", "uuid", 1, True),
            ColumnRow("Patient", "county", "text", 2, False),
            ColumnRow("PregnancyEpisode", "patient_id", "uuid", 1, False),
        ]
        self._joins = [JoinRow("PregnancyEpisode", "patient_id", "Patient", "patient_id")]

    def ping(self):
        return True

    def concepts(self):
        return self._concepts

    def columns(self, tables):
        return [c for c in self._columns if c.table in tables]

    def joins(self, tables):
        return self._joins

    def entity_tables(self):
        return ["Patient", "PregnancyEpisode"]

    def labels(self):
        return ["Attribute", "Concept", "Entity", "Persona"]

    def rel_types(self):
        return ["HAS_ATTRIBUTE", "MAPS_TO", "REFERENCES", "SERVES"]

    def node_properties(self, label):
        return ["name"]

    def run_read(self, cypher, limit):
        return []


class RetrievalOverPublishedGraph(unittest.TestCase):
    """The published CamelCase tables must survive the (normalized) entitlement filter."""

    def test_entitled_role_retrieves_camelcase_tables(self):
        kag = Neo4jKag(FakeReader(), APP)
        maria = Principal(subject="maria", tenant="rain", roles=("maria",),
                          entitlement_digest="0" * 64)
        result = kag.retrieve("How many pregnant patients are enrolled?", maria, None)
        names = [t.name for t in result.tables]
        self.assertIn("Patient", names)          # the graph's spelling is preserved
        self.assertIn("PregnancyEpisode", names)
        self.assertGreater(result.coverage, 0.0)
        self.assertTrue(result.joins)
        self.assertEqual(result.glossary_terms[0].term, "PregnantPatient")

    def test_role_less_principal_retrieves_nothing(self):
        kag = Neo4jKag(FakeReader(), APP)
        nobody = Principal(subject="x", tenant="rain", roles=(), entitlement_digest="0" * 64)
        self.assertEqual(kag.retrieve("pregnant patients", nobody, None).tables, ())


if __name__ == "__main__":
    unittest.main()
