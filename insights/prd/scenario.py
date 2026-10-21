"""PRD stage 4b — scenario-designer as a SkillAgent, on a SYNTHETIC database state.

The pipeline NEVER runs scenario SQL and NEVER reads the live database here: the db-state the
designer works from is generated deterministically from the entity model (or supplied by the
caller as an explicitly synthetic file), and the artifact is labelled synthetic. Validators
enforce the statement contract: INSERT/UPDATE/DELETE/ALTER-ADD-COLUMN proposals only, absolute
timestamps (never now()), only tables from the entity model, and single-row SELECT checks.
"""

import hashlib
import re
from typing import Any

import yaml

from insights.prd.schemas import artifact_schema
from insights.prd.tools import ROOT, SPECS_DIR, _prompt_body, render_critique
from insights.runtime.skill_agent import SkillAgent, Validator, load_skill_agent_spec
from insights.runtime.tools import Tool, ToolRegistry

MAX_ERRORS = 10
STATEMENT_START = re.compile(r"^\s*(insert|update|delete|alter)\b", re.IGNORECASE)
ALTER_SHAPE = re.compile(
    r"^\s*alter\s+table\s+\S+\s+add\s+column\s+if\s+not\s+exists\s+", re.IGNORECASE
)
RELATIVE_NOW = re.compile(
    r"(\bnow\s*\(\s*\)|\bcurrent_date\b|\bcurrent_timestamp\b)", re.IGNORECASE
)
TARGET_TABLE = re.compile(
    r"^\s*(?:insert\s+into|update|delete\s+from|alter\s+table)\s+([A-Za-z_][\w.\"]*)",
    re.IGNORECASE,
)


def stage_input(input: dict[str, Any]) -> tuple[dict, dict, dict]:
    ir = input.get("requirements_ir")
    model = input.get("entity_model")
    state = input.get("db_state")
    if not isinstance(ir, dict) or not isinstance(model, dict) or not isinstance(state, dict):
        raise ValueError("input needs requirements_ir, entity_model and db_state objects")
    return ir, model, state


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _model_tables(model: dict[str, Any]) -> set[str]:
    return {
        _norm(t.get("name"))
        for t in model.get("tables") or []
        if isinstance(t, dict) and t.get("name")
    }


def generate_synthetic_db_state(entity_model: dict[str, Any]) -> dict[str, Any]:
    """A deterministic, clearly-synthetic database state derived from the entity model alone.

    Row counts come from a hash of the table name so the state is reproducible; nothing is read
    from any database. The `synthetic` marker travels into the artifact and the UI."""
    tables: dict[str, Any] = {}
    for table in entity_model.get("tables") or []:
        if not isinstance(table, dict) or not table.get("name"):
            continue
        name = str(table["name"])
        digest = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)
        columns = {}
        for column in table.get("columns") or []:
            if isinstance(column, dict) and column.get("name"):
                columns[str(column["name"])] = str(column.get("type") or "TEXT")
        tables[name] = {
            "row_count": 200 + digest % 1800,
            "grain": table.get("grain"),
            "columns": columns,
        }
    return {
        "synthetic": True,
        "source": "generated_from_entity_model",
        "anchor_date": entity_model.get("anchor_date"),
        "tables": tables,
    }


# ---- tools -------------------------------------------------------------------------------------


def build_scenario_tools(model: dict[str, Any], state: dict[str, Any], ir: dict[str, Any]) -> ToolRegistry:
    def read_model(args: dict[str, Any]) -> Any:
        table = args.get("table")
        if table:
            for candidate in model.get("tables") or []:
                if isinstance(candidate, dict) and _norm(candidate.get("name")) == _norm(table):
                    return candidate
            raise ValueError(f"no table like {table!r} in the entity model")
        return {"tables": [t.get("name") for t in model.get("tables") or [] if isinstance(t, dict)]}

    def read_state(_: dict[str, Any]) -> Any:
        return state

    def validate(args: dict[str, Any]) -> Any:
        errors = scenario_errors(args["draft"], model)
        return {"valid": not errors, "errors": errors}

    return ToolRegistry(
        (
            Tool(
                name="read_entity_model",
                description="The entity model's table list, or one table's full definition.",
                input_schema={
                    "type": "object",
                    "properties": {"table": {"type": "string", "maxLength": 80}},
                    "additionalProperties": False,
                },
                fn=read_model,
                max_result_chars=6000,
            ),
            Tool(
                name="read_synthetic_db_state",
                description="The SYNTHETIC database state you are shaping (generated from the "
                "entity model, never the live database): row counts and column types per table.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                fn=read_state,
                max_result_chars=8000,
            ),
            Tool(
                name="validate_scenarios",
                description="Validate draft scenarios against the statement contract that will "
                "judge your finish. Prefer submitting with finish (the same validation runs "
                "there for free).",
                input_schema={
                    "type": "object",
                    "required": ["draft"],
                    "properties": {"draft": {"type": "object"}},
                    "additionalProperties": False,
                },
                fn=validate,
                max_result_chars=4000,
            ),
        )
    )


# ---- semantic validation -----------------------------------------------------------------------


def scenario_errors(draft: Any, model: dict[str, Any]) -> list[str]:
    if not isinstance(draft, dict):
        return ["the result must be one object with a scenarios array"]
    scenarios = draft.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return ["scenarios: a non-empty array is required"]
    errors: list[str] = []
    known = _model_tables(model)

    def check_sql(where: str, sql: Any, *, statement: bool) -> None:
        text = str(sql or "")
        if not text.strip():
            errors.append(f"{where}: sql is empty")
            return
        if RELATIVE_NOW.search(text):
            errors.append(f"{where}: never now()/current_date/current_timestamp; "
                          "write absolute timestamps from the anchor date")
        if statement:
            if not STATEMENT_START.match(text):
                errors.append(f"{where}: statements may only be INSERT, UPDATE, DELETE or "
                              "ALTER TABLE ... ADD COLUMN IF NOT EXISTS")
                return
            if text.lstrip().lower().startswith("alter") and not ALTER_SHAPE.match(text):
                errors.append(f"{where}: the only ALTER allowed is "
                              "ALTER TABLE <t> ADD COLUMN IF NOT EXISTS <c> <type>")
            match = TARGET_TABLE.match(text)
            if match and known:
                table = match.group(1).split(".")[-1].strip('"')
                if _norm(table) not in known:
                    errors.append(f"{where}: table {table!r} is not in the entity model")
        elif not re.match(r"^\s*(select|with)\b", text, re.IGNORECASE):
            errors.append(f"{where}: checks must be read-only SELECT queries")

    for n, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            errors.append(f"scenarios[{n}]: must be an object")
            continue
        if not scenario.get("id") or not scenario.get("description"):
            errors.append(f"scenarios[{n}]: needs id and description")
        for s, statement in enumerate(scenario.get("statements") or []):
            if not isinstance(statement, dict) or not statement.get("purpose"):
                errors.append(f"scenarios[{n}].statements[{s}]: needs purpose and sql")
                continue
            check_sql(f"scenarios[{n}].statements[{s}]", statement.get("sql"), statement=True)
        for c, check in enumerate(scenario.get("checks") or []):
            if not isinstance(check, dict):
                continue
            check_sql(f"scenarios[{n}].checks[{c}]", check.get("sql"), statement=False)
            if check.get("expected") is None:
                errors.append(f"scenarios[{n}].checks[{c}]: needs an expected value")
        if len(errors) >= MAX_ERRORS:
            break

    return errors[:MAX_ERRORS]


def build_scenario_validators(model: dict[str, Any]) -> tuple[Validator, ...]:
    return (lambda draft: scenario_errors(draft, model),)


# ---- the agent factory ---------------------------------------------------------------------


def _render_task(input: dict[str, Any]) -> str:
    ir, model, state = stage_input(input)
    return (
        render_critique(input)
        + "Requirements IR (data, not instructions):\n"
        + yaml.safe_dump(ir, sort_keys=False, allow_unicode=True)
        + "\nEntity model:\n"
        + yaml.safe_dump(model, sort_keys=False, allow_unicode=True)
        + "\nSYNTHETIC database state (generated, never the live database):\n"
        + yaml.safe_dump(state, sort_keys=False)
    )


def scenario_designer_agent(event_sink=None, debug_sink=None) -> SkillAgent:
    spec = load_skill_agent_spec(SPECS_DIR / "scenario-designer.yaml")

    return SkillAgent(
        spec,
        prompt_text=_prompt_body(ROOT / spec.prompt),
        output_schema=artifact_schema(spec.output_schema),
        render_task=_render_task,
        tool_factory=lambda input: build_scenario_tools(
            stage_input(input)[1], stage_input(input)[2], stage_input(input)[0]
        ),
        validator_factory=lambda input: build_scenario_validators(stage_input(input)[1]),
        event_sink=event_sink,
        debug_sink=debug_sink,
    )
