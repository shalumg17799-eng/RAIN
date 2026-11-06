"""Typed, read-only tools for skill agents.

A Tool is a named callable with a JSON Schema for its arguments. The registry is the only way an
agent touches files, catalogs or validators: arguments are schema-validated before dispatch, the
result is JSON-serialized and size-capped before it reaches a prompt, and a tool failure comes
back as an error text, never an exception, so the agent's loop stays bounded. Tools must be
read-only; nothing here provides a write path.
"""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import jsonschema

TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
DEFAULT_MAX_RESULT_CHARS = 8000


class ToolError(ValueError):
    """A tool definition is invalid (a dispatch problem is returned as text, never raised)."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[[dict[str, Any]], Any]
    max_result_chars: int = DEFAULT_MAX_RESULT_CHARS


@dataclass(frozen=True)
class ToolOutcome:
    ok: bool
    text: str
    """The JSON-serialized (possibly truncated) result, or the error description."""


@dataclass(frozen=True)
class ToolRegistry:
    tools: tuple[Tool, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for tool in self.tools:
            if not TOOL_NAME_RE.match(tool.name):
                raise ToolError(f"tool name {tool.name!r} is not a lowercase identifier")
            if tool.name in seen:
                raise ToolError(f"duplicate tool name {tool.name!r}")
            seen.add(tool.name)
            if not tool.description.strip():
                raise ToolError(f"tool {tool.name!r} needs a description")
            try:
                jsonschema.Draft202012Validator.check_schema(tool.input_schema)
            except jsonschema.SchemaError as exc:
                raise ToolError(f"tool {tool.name!r} has an invalid schema: {exc.message}") from exc
            if tool.max_result_chars < 200:
                raise ToolError(f"tool {tool.name!r} max_result_chars must be at least 200")

    def names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.tools)

    def get(self, name: str) -> Tool | None:
        return next((tool for tool in self.tools if tool.name == name), None)

    def describe(self) -> str:
        """One prompt block naming every tool, what it does and its argument schema."""
        if not self.tools:
            return "No tools are available."
        lines = ["Available tools:"]
        for tool in self.tools:
            schema = json.dumps(tool.input_schema, separators=(",", ":"), ensure_ascii=False)
            lines.append(f"- {tool.name}: {tool.description}\n  arguments schema: {schema}")
        return "\n".join(lines)

    def invoke(self, name: str, args: Any) -> ToolOutcome:
        """Validate and run one tool. Never raises for a bad call: the agent sees the error text."""
        tool = self.get(name)
        if tool is None:
            known = ", ".join(self.names()) or "(none)"
            return ToolOutcome(False, f"unknown tool {name!r}; available tools: {known}")
        if not isinstance(args, dict):
            return ToolOutcome(False, f"tool {name!r} arguments must be a JSON object")
        errors = sorted(
            jsonschema.Draft202012Validator(tool.input_schema).iter_errors(args),
            key=lambda e: list(e.path),
        )
        if errors:
            where = "/".join(str(p) for p in errors[0].path) or "(root)"
            return ToolOutcome(False, f"invalid arguments at {where}: {errors[0].message[:200]}")
        try:
            result = tool.fn(args)
        except Exception as exc:  # a tool bug must not break the loop
            return ToolOutcome(False, f"tool failed: {type(exc).__name__}: {str(exc)[:200]}")
        try:
            text = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return ToolOutcome(False, f"tool {name!r} returned a value that is not JSON-serializable")
        if len(text) > tool.max_result_chars:
            dropped = len(text) - tool.max_result_chars
            text = text[: tool.max_result_chars] + f" ...[truncated {dropped} chars]"
        return ToolOutcome(True, text)
