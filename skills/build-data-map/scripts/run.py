"""build-data-map: the deterministic PRD stage 4 as a registry skill. No LLM.

Builds the lower ontology from the entity model, audits it against the source CSV headers and
catalog snapshot given in the input, and returns a routing label: near-miss names go back to
the entity designer (refine_entity_model, with the specific mismatches as the critique);
everything else flows forward as ok."""

from typing import Any

from insights.prd.datamap import build_lower_ontology, compare_schema, datamap_label


def run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    entity_model = input["entity_model"]
    if not isinstance(entity_model, dict):
        raise ValueError("entity_model must be an object")
    source = input.get("source_schema") if isinstance(input.get("source_schema"), dict) else {}
    catalog = input.get("catalog_schema") if isinstance(input.get("catalog_schema"), dict) else {}

    lower = build_lower_ontology(entity_model)
    schema_audit = compare_schema(entity_model, source, catalog)
    label, critique = datamap_label(schema_audit)
    ctx["emit"]("datamap_nodes", len(lower["nodes"]))
    ctx["emit"]("datamap_edges", len(lower["edges"]))
    if label != "ok":
        ctx["emit"]("datamap_near_miss")
    return {
        "label": label,
        "critique": critique,
        "lower_ontology": lower,
        "schema_audit": schema_audit,
    }
