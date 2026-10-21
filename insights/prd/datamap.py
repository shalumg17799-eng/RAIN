"""PRD stage 4 — the deterministic data map: lower ontology build, schema audit, ontology audit.

No LLM anywhere in this module. It is the single implementation behind the build-data-map
registry skill, the pipeline's stage 4, and the agents' self-check tools. The audit DECIDES
nothing by itself; `datamap_label` turns its findings into a routing label for the graph:
near-miss names (a model table or column that almost matches a source one) are treated as
defects worth one bounded refine, while genuinely new proposed tables stay review items.
"""

import re
from difflib import SequenceMatcher
from typing import Any

MAX_CRITIQUE_ITEMS = 6


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"stage output must contain a {name} list")
    return value


def _entity_columns(table: dict[str, Any]) -> list[str]:
    raw = table.get("columns", [])
    if not isinstance(raw, list):
        return []
    return [item if isinstance(item, str) else str(item.get("name", "")) for item in raw if item]


def compare_schema(
    entity_model: dict[str, Any],
    source_schema: dict[str, list[str]],
    catalog_schema: dict[str, list[str]],
) -> dict[str, Any]:
    """Compare proposed entities with CSV and PostgreSQL names; similar names remain review items."""
    tables = _require_list(entity_model.get("tables"), "tables")
    model_tables = {str(table.get("name", "")): table for table in tables if table.get("name")}
    model_by_norm = {_norm(name): (name, table) for name, table in model_tables.items()}
    source_by_norm = {_norm(name): (name, columns) for name, columns in source_schema.items()}
    catalog_by_norm = {_norm(name): (name, columns) for name, columns in catalog_schema.items()}
    table_comparisons = []
    for source_name, source_columns in sorted(source_schema.items()):
        model_pair = model_by_norm.get(_norm(source_name))
        catalog_pair = catalog_by_norm.get(_norm(source_name))
        similar_model_tables = []
        if model_pair is None:
            similar_model_tables = [
                {"candidate": name, "similarity": round(ratio, 2)}
                for ratio, name in sorted(
                    (
                        (SequenceMatcher(None, _norm(source_name), _norm(name)).ratio(), name)
                        for name in model_tables
                    ),
                    reverse=True,
                )
                if ratio >= 0.55
            ][:3]
        if model_pair:
            entity_columns = {_norm(name) for name in _entity_columns(model_pair[1])}
            missing = [name for name in source_columns if _norm(name) not in entity_columns]
            candidates = []
            for name in missing:
                best = max(_entity_columns(model_pair[1]), key=lambda value: SequenceMatcher(None, _norm(name), _norm(value)).ratio(), default="")
                ratio = SequenceMatcher(None, _norm(name), _norm(best)).ratio() if best else 0.0
                if ratio >= 0.55:
                    candidates.append({"source_column": name, "candidate": best, "similarity": round(ratio, 2)})
        else:
            missing = source_columns
            candidates = []
        catalog_columns = {_norm(name) for name in catalog_pair[1]} if catalog_pair else set()
        table_comparisons.append({
            "source_table": source_name,
            "entity_model_table": model_pair[0] if model_pair else None,
            "similar_entity_model_tables": similar_model_tables,
            "catalog_table": catalog_pair[0] if catalog_pair else None,
            "source_columns_missing_from_entity_model": missing,
            "similar_column_candidates": candidates,
            "source_columns_missing_from_catalog": [name for name in source_columns if _norm(name) not in catalog_columns],
        })
    unmatched_model = sorted(name for name in model_tables if _norm(name) not in source_by_norm)
    catalog_tables_not_in_source = sorted(name for name in catalog_schema if _norm(name) not in source_by_norm)
    return {
        "source_table_count": len(source_schema),
        "source_column_count": sum(len(columns) for columns in source_schema.values()),
        "entity_model_table_count": len(model_tables),
        "catalog_table_count": len(catalog_schema),
        "tables_not_in_source": unmatched_model,
        "source_tables_not_in_catalog": sorted(name for name in source_schema if _norm(name) not in catalog_by_norm),
        "catalog_tables_not_in_source": catalog_tables_not_in_source,
        "tables": table_comparisons,
    }


def build_lower_ontology(entity_model: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    table_ids: dict[str, str] = {}
    for table in _require_list(entity_model.get("tables"), "tables"):
        name = str(table["name"])
        table_id = f"E-{_norm(name)}"
        table_ids[name] = table_id
        nodes.append({"id": table_id, "kind": "Entity", "name": name, "source_system": table.get("source_system"), "grain": table.get("grain"), "primary_key": table.get("primary_key")})
        for column in table.get("columns", []):
            col = column if isinstance(column, dict) else {"name": column}
            col_name = str(col.get("name", ""))
            if not col_name:
                continue
            column_id = f"A-{_norm(name)}-{_norm(col_name)}"
            nodes.append({"id": column_id, "kind": "Attribute", "name": col_name, "data_type": col.get("type"), "nullable": col.get("nullable"), "note": col.get("note")})
            edges.append({"id": f"HAS-{table_id}-{column_id}", "type": "HAS_ATTRIBUTE", "from": table_id, "to": column_id})
    for relation in entity_model.get("relationships", []):
        source = str(relation.get("from_table", ""))
        target = str(relation.get("to_table", ""))
        if source in table_ids and target in table_ids:
            edges.append({"id": f"REF-{len(edges)+1:04d}", "type": "REFERENCES", "from": table_ids[source], "to": table_ids[target], "from_column": relation.get("from_column"), "to_column": relation.get("to_column"), "declared": relation.get("declared", True)})
    return {"nodes": nodes, "edges": edges}


def audit_upper_ontology(upper: dict[str, Any], lower: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
    nodes = _require_list(upper.get("nodes"), "nodes")
    edges = _require_list(upper.get("edges"), "edges")
    nodes_by_id = {str(node.get("id")): node for node in [*nodes, *lower["nodes"]]}
    invalid_edges = [
        edge for edge in edges
        if str(edge.get("from")) not in nodes_by_id or str(edge.get("to")) not in nodes_by_id
    ]
    invalid_edge_kinds = []
    for edge in edges:
        source = nodes_by_id.get(str(edge.get("from")), {})
        target = nodes_by_id.get(str(edge.get("to")), {})
        edge_type = edge.get("type")
        valid = (
            edge_type == "SERVES" and source.get("kind") == "Persona" and target.get("kind") == "Concept"
            or edge_type == "RELATES_TO" and source.get("kind") == target.get("kind") == "Concept"
            or edge_type == "MAPS_TO" and source.get("kind") == "Concept" and target.get("kind") in {"Entity", "Attribute"}
        )
        if not valid:
            invalid_edge_kinds.append(edge)
    personas = requirements.get("personas", [])
    personas = personas.values() if isinstance(personas, dict) else personas
    persona_names = {_norm(str(p.get("persona_id") or p.get("id") or p.get("name", ""))) for p in personas if isinstance(p, dict)}
    ontology_personas = {_norm(str(node.get("persona_id") or node.get("name", ""))) for node in nodes if node.get("kind") == "Persona"}
    return {
        "concept_nodes": sum(node.get("kind") == "Concept" for node in nodes),
        "persona_nodes": sum(node.get("kind") == "Persona" for node in nodes),
        "edge_count": len(edges),
        "edge_counts_by_type": {kind: sum(edge.get("type") == kind for edge in edges) for kind in ("SERVES", "RELATES_TO", "MAPS_TO")},
        "invalid_edge_references": invalid_edges,
        "invalid_edge_kinds": invalid_edge_kinds,
        "concepts_missing_synonyms": [node.get("id") for node in nodes if node.get("kind") == "Concept" and not node.get("synonyms")],
        "concepts_missing_definitions": [node.get("id") for node in nodes if node.get("kind") == "Concept" and not node.get("definition")],
        "personas_missing_from_ontology": sorted(persona_names - ontology_personas),
        "ontology_personas_not_in_requirements": sorted(ontology_personas - persona_names),
        "unmapped_concepts": [node.get("id") for node in nodes if node.get("kind") == "Concept" and node.get("unmapped") is True],
    }


def datamap_label(schema_audit: dict[str, Any]) -> tuple[str, str | None]:
    """(label, critique) for the graph: near-miss names route back to the entity designer once,
    bounded by max_refines; everything else is a review item and flows forward as `ok`."""
    near_misses: list[str] = []
    for comparison in schema_audit.get("tables") or []:
        for similar in comparison.get("similar_entity_model_tables") or []:
            near_misses.append(
                f"model table {similar['candidate']!r} nearly matches source table "
                f"{comparison['source_table']!r} (similarity {similar['similarity']}); align the "
                "name or declare it a new table"
            )
        for similar in comparison.get("similar_column_candidates") or []:
            near_misses.append(
                f"in {comparison['source_table']!r}, model column {similar['candidate']!r} nearly "
                f"matches source column {similar['source_column']!r}; align the name"
            )
    if near_misses:
        return "refine_entity_model", "; ".join(near_misses[:MAX_CRITIQUE_ITEMS])
    return "ok", None
