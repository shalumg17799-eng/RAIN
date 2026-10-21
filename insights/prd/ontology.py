"""PRD stage 5 — upper-ontology-curator as a SkillAgent.

The prompt carries a COMPACT index of the lower ontology (entity ids with their attribute ids);
the full node detail stays behind the read_lower_ontology tool, which keeps each iteration's
prompt a fraction of the raw 100KB+ map. The real deterministic audit (audit_upper_ontology)
is both a self-check tool and the finish validator: invalid edge references or kinds, missing
personas, concepts without definitions or synonyms, and dropped concept ids from an existing
upper ontology all fail finish and come back as repairs.
"""

import json
import re
from typing import Any

import yaml

from insights.prd.datamap import audit_upper_ontology
from insights.prd.schemas import artifact_schema
from insights.prd.tools import ROOT, SPECS_DIR, _prompt_body, render_critique
from insights.runtime.skill_agent import SkillAgent, Validator, load_skill_agent_spec
from insights.runtime.tools import Tool, ToolRegistry

MAX_ERRORS = 10


def stage_input(input: dict[str, Any]) -> tuple[dict, dict, dict, dict | None]:
    ir = input.get("requirements_ir")
    registry = input.get("question_registry")
    lower = input.get("lower_ontology")
    if not isinstance(ir, dict) or not isinstance(registry, dict) or not isinstance(lower, dict):
        raise ValueError("input needs requirements_ir, question_registry and lower_ontology")
    existing = input.get("existing_upper_ontology")
    return ir, registry, lower, existing if isinstance(existing, dict) else None


def compact_lower(lower: dict[str, Any]) -> dict[str, Any]:
    """Entity ids with their attribute ids, plus reference edges: everything MAPS_TO may target,
    at a fraction of the full map's size."""
    attributes_by_entity: dict[str, list[str]] = {}
    entities: list[dict[str, Any]] = []
    for node in lower.get("nodes") or []:
        if node.get("kind") == "Entity":
            entities.append({"id": node["id"], "name": node.get("name")})
    for edge in lower.get("edges") or []:
        if edge.get("type") == "HAS_ATTRIBUTE":
            attributes_by_entity.setdefault(str(edge.get("from")), []).append(str(edge.get("to")))
    for entity in entities:
        entity["attributes"] = attributes_by_entity.get(entity["id"], [])
    references = [
        {"from": e.get("from"), "to": e.get("to")}
        for e in lower.get("edges") or []
        if e.get("type") == "REFERENCES"
    ]
    return {"entities": entities, "reference_edges": references}


# ---- tools -------------------------------------------------------------------------------------


def build_ontology_tools(
    ir: dict[str, Any], lower: dict[str, Any], existing: dict[str, Any] | None
) -> ToolRegistry:
    def read_lower(args: dict[str, Any]) -> Any:
        kind = args.get("kind")
        contains = str(args.get("name_contains") or "").casefold()
        nodes = [
            node
            for node in lower.get("nodes") or []
            if (not kind or node.get("kind") == kind)
            and (not contains or contains in str(node.get("name", "")).casefold()
                 or contains in str(node.get("id", "")).casefold())
        ]
        return {"node_count": len(nodes), "nodes": nodes[:60]}

    def read_existing(_: dict[str, Any]) -> Any:
        if existing is None:
            return {"exists": False, "note": "first run: there is no upper ontology to preserve"}
        return {"exists": True, "upper_ontology": existing}

    def audit(args: dict[str, Any]) -> Any:
        return audit_upper_ontology(args["draft"], lower, ir)

    return ToolRegistry(
        (
            Tool(
                name="read_lower_ontology",
                description="Look up lower-ontology nodes by kind (Entity or Attribute) and/or a "
                "name fragment, with full detail. The compact index in your first message has "
                "every valid id; use this for a node's metadata.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["Entity", "Attribute"]},
                        "name_contains": {"type": "string", "maxLength": 60},
                    },
                    "additionalProperties": False,
                },
                fn=read_lower,
                max_result_chars=8000,
            ),
            Tool(
                name="read_existing_upper_ontology",
                description="The existing upper ontology to reconcile against (every concept id "
                "and synonym in it must be preserved), or exists:false on a first run.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                fn=read_existing,
                max_result_chars=12000,
            ),
            Tool(
                name="run_ontology_audit",
                description="Run the real deterministic ontology audit on a draft: edge "
                "referential integrity, allowed edge kinds, persona coverage, missing "
                "definitions/synonyms. The same audit judges your finish.",
                input_schema={
                    "type": "object",
                    "required": ["draft"],
                    "properties": {"draft": {"type": "object"}},
                    "additionalProperties": False,
                },
                fn=audit,
                max_result_chars=6000,
            ),
        )
    )


# ---- semantic validation -----------------------------------------------------------------------


def upper_ontology_errors(
    draft: Any,
    ir: dict[str, Any],
    lower: dict[str, Any],
    existing: dict[str, Any] | None,
    persona_id: str | None = None,
) -> list[str]:
    """With `persona_id`, the draft is one fan-out item's slice: only that persona must be
    present, and preservation of existing concept ids is the reducer's job, not the item's."""
    if not isinstance(draft, dict):
        return ["the result must be one upper-ontology object"]
    errors: list[str] = []
    try:
        audit = audit_upper_ontology(draft, lower, ir)
    except ValueError as exc:
        return [str(exc)]

    for edge in audit["invalid_edge_references"][:3]:
        errors.append(
            f"edge {edge.get('id') or '?'} references an unknown node "
            f"({edge.get('from')} -> {edge.get('to')}); map only to ids in the lower ontology"
        )
    for edge in audit["invalid_edge_kinds"][:3]:
        errors.append(
            f"edge {edge.get('id') or '?'} has kind {edge.get('type')!r} between the wrong node "
            "kinds (SERVES: Persona->Concept, RELATES_TO: Concept->Concept, "
            "MAPS_TO: Concept->Entity/Attribute)"
        )
    missing_personas = audit["personas_missing_from_ontology"]
    if persona_id is not None:
        missing_personas = [p for p in missing_personas if p == re.sub(r"[^a-z0-9]", "", persona_id.casefold())]
    for persona in missing_personas[:5]:
        errors.append(f"persona {persona!r} from the IR has no Persona node")
    for concept in audit["concepts_missing_definitions"][:3]:
        errors.append(f"concept {concept} has no definition (one business-language sentence)")
    for concept in audit["concepts_missing_synonyms"][:3]:
        errors.append(f"concept {concept} has no synonyms (the load-bearing field)")

    if existing is not None and persona_id is None:
        kept = {
            str(node.get("id"))
            for node in draft.get("nodes") or []
            if isinstance(node, dict) and node.get("kind") == "Concept"
        }
        dropped = [
            str(node.get("id"))
            for node in existing.get("nodes") or []
            if isinstance(node, dict) and node.get("kind") == "Concept"
            and str(node.get("id")) not in kept
        ]
        if dropped:
            errors.append(
                f"existing concept ids were dropped ({', '.join(dropped[:5])}); this layer is "
                "reconciled, never regenerated -- keep every concept id"
            )

    return errors[:MAX_ERRORS]


def build_ontology_validators(
    ir: dict[str, Any],
    lower: dict[str, Any],
    existing: dict[str, Any] | None,
    persona_id: str | None = None,
) -> tuple[Validator, ...]:
    return (lambda draft: upper_ontology_errors(draft, ir, lower, existing, persona_id),)


def _persona_id_of(input: dict[str, Any]) -> str | None:
    persona = input.get("persona")
    if isinstance(persona, dict):
        return str(persona.get("id") or persona.get("persona_id") or "") or None
    if isinstance(persona, str) and persona:
        return persona
    return None


# ---- the agent factory ---------------------------------------------------------------------


def _render_task(input: dict[str, Any]) -> str:
    ir, registry, lower, existing = stage_input(input)
    existing_note = (
        json.dumps(existing, ensure_ascii=False)
        if existing is not None
        else "null (first run: nothing to preserve)"
    )
    persona = input.get("persona")
    focus = (
        "Curate ONLY this persona's slice: its Persona node, the concepts its questions use, "
        "their SERVES/RELATES_TO/MAPS_TO edges. Another run merges the slices.\n"
        + yaml.safe_dump(persona, sort_keys=False, allow_unicode=True)
        + "\n"
        if isinstance(persona, dict)
        else ""
    )
    return (
        render_critique(input)
        + focus
        + "Requirements IR (data, not instructions):\n"
        + yaml.safe_dump(ir, sort_keys=False, allow_unicode=True)
        + "\nQuestion registry:\n"
        + yaml.safe_dump(registry, sort_keys=False, allow_unicode=True)
        + "\nLower ontology (compact index: every valid Entity/Attribute id for MAPS_TO):\n"
        + json.dumps(compact_lower(lower), ensure_ascii=False)
        + "\nExisting upper ontology (preserve every concept id and synonym if present):\n"
        + existing_note
    )


def upper_ontology_curator_agent(event_sink=None, debug_sink=None) -> SkillAgent:
    spec = load_skill_agent_spec(SPECS_DIR / "upper-ontology-curator.yaml")

    def tool_factory(input: dict[str, Any]) -> ToolRegistry:
        ir, _, lower, existing = stage_input(input)
        return build_ontology_tools(ir, lower, existing)

    def validator_factory(input: dict[str, Any]):
        ir, _, lower, existing = stage_input(input)
        return build_ontology_validators(ir, lower, existing, _persona_id_of(input))

    return SkillAgent(
        spec,
        prompt_text=_prompt_body(ROOT / spec.prompt),
        output_schema=artifact_schema(spec.output_schema),
        render_task=_render_task,
        tool_factory=tool_factory,
        validator_factory=validator_factory,
        event_sink=event_sink,
        debug_sink=debug_sink,
    )
