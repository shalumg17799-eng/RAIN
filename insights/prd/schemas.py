"""Output JSON Schemas for the PRD design stages, shared by the pipeline and the skill agents."""

from typing import Any

_ITEM = {"type": "object", "additionalProperties": True}

SCHEMAS: dict[str, dict[str, Any]] = {
    "requirements-interpreter": {
        "type": "object",
        "properties": {
            "mode": {"type": "string"}, "domain": {"type": ["string", "null"]},
            "anchor_date": {"type": ["string", "null"]},
            "personas": {"type": "array", "items": _ITEM},
            "questions": {"type": "array", "items": _ITEM},
            "committed_figures": {"type": "array", "items": _ITEM},
            "source_systems": {"type": "array"}, "entity_hints": {"type": "array"},
            "narrative_events": {"type": "array", "items": _ITEM},
            "constraints": {"type": "array"}, "open_items": {"type": "array", "items": _ITEM},
        },
        "required": ["mode", "personas", "questions", "committed_figures", "source_systems", "entity_hints", "narrative_events", "constraints", "open_items"],
        "additionalProperties": True,
    },
    "persona-question-designer": {
        "type": "object",
        "properties": {"questions": {"type": "array", "items": {"type": "object", "properties": {"persona_id": {"type": "string"}, "text": {"type": "string"}, "tier": {"type": "string"}, "signal": {"type": "string"}, "is_data_question": {"type": "boolean"}}, "required": ["persona_id", "text", "tier"], "additionalProperties": True}}},
        "required": ["questions"], "additionalProperties": True,
    },
    "entity-model-designer": {
        "type": "object",
        "properties": {"anchor_date": {"type": ["string", "null"]}, "tables": {"type": "array", "items": _ITEM}, "relationships": {"type": "array", "items": _ITEM}, "messiness_profile": {"type": "object"}},
        "required": ["tables", "relationships"], "additionalProperties": True,
    },
    "scenario-designer": {
        "type": "object", "properties": {"scenarios": {"type": "array", "items": _ITEM}},
        "required": ["scenarios"], "additionalProperties": True,
    },
    "upper-ontology-curator": {
        "type": "object",
        "properties": {"nodes": {"type": "array", "items": _ITEM}, "edges": {"type": "array", "items": _ITEM}, "duplicate_candidates": {"type": "array", "items": _ITEM}, "coverage_gaps_detected": {"type": "array", "items": _ITEM}},
        "required": ["nodes", "edges", "duplicate_candidates", "coverage_gaps_detected"],
        "additionalProperties": True,
    },
}


def artifact_schema(stage: str) -> dict[str, Any]:
    try:
        return SCHEMAS[stage]
    except KeyError:
        raise ValueError(f"no artifact schema is defined for {stage}") from None
