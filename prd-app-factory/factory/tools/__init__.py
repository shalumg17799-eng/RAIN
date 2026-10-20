"""Tool registry. A tool is a JSON-schema'd function an agent may call; each
agent gets only the tools its stages need (least privilege)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from factory.apppack import AppPack


@dataclass
class RunContext:
    pack: AppPack
    agent: str
    mode: str = ""
    task: dict = field(default_factory=dict)
    finished: dict | None = None
    approved_gates: set[str] = field(default_factory=set)


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable[..., Any]

    def definition(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.schema,
                "eager_input_streaming": True}


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, properties: dict, required: list[str] | None = None):
    """Register a tool. The function is called as fn(ctx, **input)."""
    schema = {"type": "object", "properties": properties, "required": required or [],
              "additionalProperties": False}

    def wrap(fn):
        REGISTRY[name] = Tool(name, description, schema, fn)
        return fn
    return wrap


def get(names: list[str]) -> list[Tool]:
    missing = [n for n in names if n not in REGISTRY]
    if missing:
        raise KeyError(f"unknown tools: {missing}")
    return [REGISTRY[n] for n in names]


# Register every tool module.
from factory.tools import common, requirements, data, knowledge, appbuilder, release  # noqa: E402,F401
