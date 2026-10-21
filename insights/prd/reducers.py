"""Deterministic reduce steps for the PRD graph's fan-outs, plus the run finalizer. No LLM.

A map step's results arrive as $.fanout.<id> entries {"attempt", "index", "item", "output"};
reducers keep only the highest attempt (a refine loop re-dispatches the whole map), judge the
items, merge them, and return a routing label.
"""

import re
from typing import Any

from insights.prd.datamap import audit_upper_ontology
from insights.prd.questions import dedupe, question_registry_errors

MAX_CRITIQUE_ITEMS = 5


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def latest_entries(results: Any) -> list[dict[str, Any]]:
    entries = [e for e in (results or []) if isinstance(e, dict)]
    if not entries:
        return []
    top = max(int(e.get("attempt") or 0) for e in entries)
    return sorted(
        (e for e in entries if int(e.get("attempt") or 0) == top),
        key=lambda e: int(e.get("index") or 0),
    )


def _escalations(entries: list[dict[str, Any]]) -> list[str]:
    problems = []
    for entry in entries:
        output = entry.get("output") or {}
        if output.get("label") != "ok":
            item = entry.get("item")
            name = item.get("id") if isinstance(item, dict) else item
            problems.append(f"item {name!r}: {str(output.get('reason') or output.get('label'))[:160]}")
    return problems


# ---- question registry -------------------------------------------------------------------------


def reduce_question_registry(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    ir = input["requirements_ir"]
    entries = latest_entries(input.get("results"))
    if not entries:
        return {"label": "escalate", "reason": "no fan-out results arrived", "critique": None}
    failed = _escalations(entries)
    if failed:
        return {
            "label": "escalate",
            "reason": "persona runs escalated: " + "; ".join(failed[:MAX_CRITIQUE_ITEMS]),
            "critique": None,
        }
    merged: list[Any] = []
    for entry in entries:
        registry = (entry.get("output") or {}).get("question_registry") or {}
        merged.extend(q for q in registry.get("questions") or [] if isinstance(q, dict))
    unique, removed = dedupe(merged)
    errors = question_registry_errors({"questions": unique}, ir)
    ctx["emit"]("questions_merged", len(unique))
    if removed:
        ctx["emit"]("questions_deduped", len(removed))
    if errors:
        return {
            "label": "escalate",
            "reason": "merged registry invalid: " + "; ".join(errors[:MAX_CRITIQUE_ITEMS]),
            "critique": None,
        }
    return {
        "label": "ok",
        "reason": None,
        "critique": None,
        "question_registry": {"questions": unique},
        "removed_duplicates": len(removed),
    }


# ---- upper ontology ----------------------------------------------------------------------------


def _merge_upper(slices: list[dict[str, Any]]) -> dict[str, Any]:
    """Union the per-persona slices: Personas by id, Concepts by normalized name (first id wins,
    synonyms union), edges rewritten through the concept-id remap and deduped."""
    personas: dict[str, dict[str, Any]] = {}
    concepts: dict[str, dict[str, Any]] = {}  # by normalized name
    remap: dict[str, str] = {}
    duplicate_candidates: list[dict[str, Any]] = []
    coverage_gaps: list[Any] = []

    for piece in slices:
        for node in piece.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            if node.get("kind") == "Persona":
                personas.setdefault(str(node.get("persona_id") or node.get("id")), node)
            elif node.get("kind") == "Concept":
                key = _norm(node.get("name"))
                if key not in concepts:
                    concepts[key] = {**node, "synonyms": sorted({
                        str(s) for s in node.get("synonyms") or []
                    })}
                else:
                    kept = concepts[key]
                    remap[str(node.get("id"))] = str(kept.get("id"))
                    kept["synonyms"] = sorted(
                        {*kept.get("synonyms", []), *(str(s) for s in node.get("synonyms") or [])}
                    )
                    if not kept.get("definition") and node.get("definition"):
                        kept["definition"] = node["definition"]
                    duplicate_candidates.append(
                        {"kept": kept.get("id"), "merged": node.get("id"), "name": node.get("name")}
                    )
        coverage_gaps.extend(piece.get("coverage_gaps_detected") or [])

    edges: dict[tuple, dict[str, Any]] = {}
    for piece in slices:
        for edge in piece.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            rewritten = {
                **edge,
                "from": remap.get(str(edge.get("from")), edge.get("from")),
                "to": remap.get(str(edge.get("to")), edge.get("to")),
            }
            key = (rewritten.get("type"), rewritten.get("from"), rewritten.get("to"))
            edges.setdefault(key, rewritten)

    return {
        "nodes": [*concepts.values(), *personas.values()],
        "edges": list(edges.values()),
        "duplicate_candidates": duplicate_candidates,
        "coverage_gaps_detected": coverage_gaps,
    }


def reduce_upper_ontology(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    ir = input["requirements_ir"]
    lower = input["lower_ontology"]
    existing = input.get("existing_upper_ontology")
    entries = latest_entries(input.get("results"))
    if not entries:
        return {"label": "escalate", "reason": "no fan-out results arrived", "critique": None}
    failed = _escalations(entries)
    if failed:
        return {
            "label": "escalate",
            "reason": "persona runs escalated: " + "; ".join(failed[:MAX_CRITIQUE_ITEMS]),
            "critique": None,
        }
    merged = _merge_upper([
        (entry.get("output") or {}).get("upper_ontology") or {} for entry in entries
    ])

    problems: list[str] = []
    audit = audit_upper_ontology(merged, lower, ir)
    for edge in audit["invalid_edge_references"][:3]:
        problems.append(
            f"edge {edge.get('id') or '?'} references an unknown node "
            f"({edge.get('from')} -> {edge.get('to')})"
        )
    for edge in audit["invalid_edge_kinds"][:2]:
        problems.append(f"edge {edge.get('id') or '?'} connects the wrong node kinds")
    for persona in audit["personas_missing_from_ontology"][:3]:
        problems.append(f"persona {persona!r} has no Persona node")
    if isinstance(existing, dict):
        kept = {
            str(n.get("id")) for n in merged["nodes"] if n.get("kind") == "Concept"
        } | set(map(str, (e.get("merged") for e in merged["duplicate_candidates"])))
        dropped = [
            str(n.get("id"))
            for n in existing.get("nodes") or []
            if isinstance(n, dict) and n.get("kind") == "Concept" and str(n.get("id")) not in kept
        ]
        if dropped:
            problems.append(f"existing concept ids dropped: {', '.join(dropped[:5])}")

    ctx["emit"]("ontology_merged_concepts", audit["concept_nodes"])
    if problems:
        return {
            "label": "refine_ontology",
            "reason": None,
            "critique": "; ".join(problems[:MAX_CRITIQUE_ITEMS]),
            "upper_ontology": merged,
            "ontology_audit": audit,
        }
    return {
        "label": "ok",
        "reason": None,
        "critique": None,
        "upper_ontology": merged,
        "ontology_audit": audit,
    }


# ---- the finalizer -----------------------------------------------------------------------------


def finalize_run(input: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    steps = input.get("steps") or {}

    def output_of(step_id: str) -> dict[str, Any]:
        record = steps.get(step_id) or {}
        out = record.get("output") if isinstance(record, dict) else None
        return out if isinstance(out, dict) else {}

    stage_summary = {}
    for step_id, record in steps.items():
        if not isinstance(record, dict):
            continue
        output = record.get("output") if isinstance(record.get("output"), dict) else {}
        stage_summary[step_id] = {
            "label": record.get("label"),
            "runs": record.get("runs"),
            "confidence": output.get("confidence"),
            "reason": output.get("reason"),
        }
    datamap = output_of("datamap")
    reduce_out = output_of("ontology_reduce")
    completed = bool(reduce_out.get("upper_ontology"))
    return {
        "run_report": {
            "completed": completed,
            "stages": stage_summary,
            "schema_audit_summary": {
                "entity_model_tables": (datamap.get("schema_audit") or {}).get("entity_model_table_count"),
                "tables_not_in_source": (datamap.get("schema_audit") or {}).get("tables_not_in_source"),
            },
            "ontology_audit": reduce_out.get("ontology_audit"),
        }
    }
