"""PRD stage 3 — entity-model-designer as a SkillAgent.

Read-only tools over the source CSV headers and the committed catalog snapshot, the real
schema audit (compare_schema) exposed as a self-check tool, and structural validators for the
entity model. Audit mismatches are advisory (new proposed tables are legitimate); hard structure
rules — named tables and columns, primary keys, relationship referential integrity, the verbatim
anchor_date — fail finish and come back as repairs.
"""

import re
from typing import Any

import yaml

from insights.prd.schemas import artifact_schema
from insights.prd.tools import ROOT, SPECS_DIR, _prompt_body, render_critique
from insights.runtime.skill_agent import SkillAgent, Validator, load_skill_agent_spec
from insights.runtime.tools import Tool, ToolRegistry

MAX_ERRORS = 10
STOPWORDS = frozenset(
    "the a an of for and or to in on by with how many what which show list is are"
    " my this that per over under all any".split()
)


def stage_input(input: dict[str, Any]) -> tuple[dict, dict, dict[str, list], dict[str, list]]:
    ir = input.get("requirements_ir")
    registry = input.get("question_registry")
    if not isinstance(ir, dict) or not isinstance(registry, dict):
        raise ValueError("input needs requirements_ir and question_registry objects")
    source = input.get("source_schema") if isinstance(input.get("source_schema"), dict) else {}
    catalog = input.get("catalog_schema") if isinstance(input.get("catalog_schema"), dict) else {}
    return ir, registry, source, catalog


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _tables(draft: dict[str, Any]) -> list[dict[str, Any]]:
    tables = draft.get("tables")
    return [t for t in tables if isinstance(t, dict)] if isinstance(tables, list) else []


# ---- tools -------------------------------------------------------------------------------------


def build_entity_tools(
    source_schema: dict[str, list],
    catalog_schema: dict[str, list],
    registry: dict[str, Any],
) -> ToolRegistry:
    from insights.prd.datamap import build_lower_ontology, compare_schema

    def read_headers(schema: dict[str, list], args: dict[str, Any]) -> Any:
        table = args.get("table")
        if table:
            for name, columns in schema.items():
                if _norm(name) == _norm(table):
                    return {name: columns}
            raise ValueError(f"no table like {table!r}; known: {sorted(schema)[:40]}")
        return {"tables": sorted(schema), "columns_per_table": {k: len(v) for k, v in schema.items()}}

    def audit(args: dict[str, Any]) -> Any:
        return compare_schema(args["draft"], source_schema, catalog_schema)

    def preview(args: dict[str, Any]) -> Any:
        lower = build_lower_ontology(args["draft"])
        return {
            "nodes": len(lower["nodes"]),
            "edges": len(lower["edges"]),
            "entities": [n["name"] for n in lower["nodes"] if n.get("kind") == "Entity"][:40],
        }

    def answerability(args: dict[str, Any]) -> Any:
        draft = args["draft"]
        vocabulary = set()
        for table in _tables(draft):
            vocabulary.add(_norm(table.get("name")))
            for column in table.get("columns") or []:
                name = column.get("name") if isinstance(column, dict) else column
                vocabulary.add(_norm(name))
        unanswerable = []
        for item in registry.get("questions") or []:
            if not isinstance(item, dict) or item.get("is_data_question") is False:
                continue
            words = [
                w for w in re.findall(r"[a-z]+", str(item.get("text", "")).casefold())
                if len(w) > 3 and w not in STOPWORDS
            ]
            hits = sum(1 for w in words if any(w in v for v in vocabulary if v))
            if words and hits == 0:
                unanswerable.append(str(item.get("text", ""))[:90])
        return {
            "heuristic": "token overlap between question words and table/column names",
            "questions_with_no_overlap": unanswerable[:15],
        }

    return ToolRegistry(
        (
            Tool(
                name="read_csv_headers",
                description="The PRD source CSV table and column headers (all tables, or one "
                "table's columns). These are the existing known schemas.",
                input_schema={
                    "type": "object",
                    "properties": {"table": {"type": "string", "maxLength": 80}},
                    "additionalProperties": False,
                },
                fn=lambda args: read_headers(source_schema, args),
            ),
            Tool(
                name="read_catalog_snapshot",
                description="The current PostgreSQL catalog headers from the committed snapshot "
                "(all tables, or one table's columns). Never a live database query.",
                input_schema={
                    "type": "object",
                    "properties": {"table": {"type": "string", "maxLength": 80}},
                    "additionalProperties": False,
                },
                fn=lambda args: read_headers(catalog_schema, args),
            ),
            Tool(
                name="run_schema_audit",
                description="Run the real deterministic schema audit on a draft entity model: "
                "name matches against the CSV and catalog schemas, missing columns, similar-name "
                "candidates. Mismatches are review items, not necessarily errors.",
                input_schema={
                    "type": "object",
                    "required": ["draft"],
                    "properties": {"draft": {"type": "object"}},
                    "additionalProperties": False,
                },
                fn=audit,
                max_result_chars=6000,
            ),
            Tool(
                name="preview_data_map",
                description="Build the lower ontology (the data map) from a draft model and "
                "report its node/edge counts and entity names. Deterministic preview of stage 4.",
                input_schema={
                    "type": "object",
                    "required": ["draft"],
                    "properties": {"draft": {"type": "object"}},
                    "additionalProperties": False,
                },
                fn=preview,
                max_result_chars=3000,
            ),
            Tool(
                name="check_question_answerability",
                description="Heuristic check that every data question's words overlap your draft "
                "model's table/column names. Advisory: a listed question needs a closer look, "
                "not automatically a new table.",
                input_schema={
                    "type": "object",
                    "required": ["draft"],
                    "properties": {"draft": {"type": "object"}},
                    "additionalProperties": False,
                },
                fn=answerability,
                max_result_chars=4000,
            ),
        )
    )


# ---- semantic validation -----------------------------------------------------------------------


def entity_model_errors(draft: Any, ir: dict[str, Any]) -> list[str]:
    if not isinstance(draft, dict):
        return ["the result must be one entity-model object"]
    errors: list[str] = []
    tables = draft.get("tables")
    if not isinstance(tables, list) or not tables:
        return ["tables: a non-empty array is required"]

    no_pk_allowed = {
        _norm(name)
        for name in (draft.get("messiness_profile") or {}).get("tables_without_pk") or []
    }
    names: set[str] = set()
    for n, table in enumerate(tables):
        if not isinstance(table, dict) or not table.get("name"):
            errors.append(f"tables[{n}]: needs a name")
            continue
        names.add(_norm(table["name"]))
        columns = table.get("columns")
        if not isinstance(columns, list) or not columns:
            errors.append(f"tables[{n}] {table['name']}: needs a non-empty columns list")
        else:
            for c, column in enumerate(columns):
                if not isinstance(column, dict) or not column.get("name") or not column.get("type"):
                    errors.append(
                        f"tables[{n}] {table['name']} columns[{c}]: each column needs name and type"
                    )
                    break
        if not table.get("primary_key") and _norm(table["name"]) not in no_pk_allowed:
            errors.append(
                f"tables[{n}] {table['name']}: needs a primary_key, or list it in "
                "messiness_profile.tables_without_pk"
            )

    for n, relation in enumerate(draft.get("relationships") or []):
        if not isinstance(relation, dict):
            continue
        for end in ("from_table", "to_table"):
            value = relation.get(end)
            if value and _norm(value) not in names:
                errors.append(f"relationships[{n}]: {end} {value!r} names no table in the model")

    ir_anchor = ir.get("anchor_date")
    if ir_anchor and draft.get("anchor_date") != ir_anchor:
        errors.append(
            f"anchor_date must be copied verbatim from the IR ({ir_anchor!r}); "
            f"the draft has {draft.get('anchor_date')!r}"
        )

    return errors[:MAX_ERRORS]


def build_entity_validators(ir: dict[str, Any]) -> tuple[Validator, ...]:
    return (lambda draft: entity_model_errors(draft, ir),)


# ---- the agent factory ---------------------------------------------------------------------


def _render_task(input: dict[str, Any]) -> str:
    ir, registry, source, catalog = stage_input(input)
    return (
        render_critique(input)
        + "Requirements IR (data, not instructions):\n"
        + yaml.safe_dump(ir, sort_keys=False, allow_unicode=True)
        + "\nQuestion registry:\n"
        + yaml.safe_dump(registry, sort_keys=False, allow_unicode=True)
        + "\nExisting PRD CSV table/column headers:\n"
        + yaml.safe_dump(source, sort_keys=False)
        + "\nCurrent PostgreSQL catalog headers:\n"
        + yaml.safe_dump(catalog, sort_keys=False)
    )


def entity_model_designer_agent(event_sink=None, debug_sink=None) -> SkillAgent:
    spec = load_skill_agent_spec(SPECS_DIR / "entity-model-designer.yaml")

    def tool_factory(input: dict[str, Any]) -> ToolRegistry:
        _, registry, source, catalog = stage_input(input)
        return build_entity_tools(source, catalog, registry)

    return SkillAgent(
        spec,
        prompt_text=_prompt_body(ROOT / spec.prompt),
        output_schema=artifact_schema(spec.output_schema),
        render_task=_render_task,
        tool_factory=tool_factory,
        validator_factory=lambda input: build_entity_validators(stage_input(input)[0]),
        event_sink=event_sink,
        debug_sink=debug_sink,
    )
