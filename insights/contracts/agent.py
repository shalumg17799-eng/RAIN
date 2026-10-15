"""agents/<name>.yaml as data. Structure only: no expressions and no logic.

A step input value is a literal or a reference string. References:
  $.input.<path>             the request input
  $.steps.<id>.output.<path> a finished step's output (strict: a missing path is an error)
  $.refine.<path>            engine-owned refine state (attempt, max_refines, critique, history)
A route maps a label returned by the step to the next step id. Nothing else.
`validate_agent` (S3) does the cross-step checks that need the skill registry.
"""

import re
from typing import Annotated, Any

from pydantic import Field, StringConstraints, model_validator

from insights.contracts.common import Contract, Identifier, SemVer, SkillName

REF_RE = re.compile(r"^\$\.(input|steps|refine)(\.[A-Za-z_][A-Za-z0-9_]*)*$")

Ref = Annotated[str, StringConstraints(pattern=REF_RE.pattern)]


def is_ref(value: object) -> bool:
    return isinstance(value, str) and value.startswith("$.")


def _check_refs(value: Any, where: str) -> None:
    if isinstance(value, str):
        if is_ref(value) and not REF_RE.match(value):
            raise ValueError(f"{where}: malformed reference {value!r}")
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_refs(item, f"{where}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _check_refs(item, f"{where}[{index}]")


class RouteSpec(Contract):
    on: Ref
    to: dict[Identifier, Identifier] = Field(min_length=1)


class Step(Contract):
    id: Identifier
    skill: SkillName
    version: SemVer | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    route: RouteSpec | None = None

    @model_validator(mode="after")
    def _refs_are_well_formed(self) -> "Step":
        _check_refs(self.input, f"step {self.id}.input")
        return self


class AgentLimits(Contract):
    max_refines: int = Field(ge=0, le=5)
    max_tokens: int = Field(ge=1)
    deadline_ms: int = Field(ge=100)


class AgentDef(Contract):
    name: SkillName
    version: SemVer
    description: str = ""
    steps: tuple[Step, ...] = Field(min_length=1)
    output: dict[str, Ref] = Field(min_length=1)
    limits: AgentLimits

    @model_validator(mode="after")
    def _unique_step_ids(self) -> "AgentDef":
        ids = [step.id for step in self.steps]
        if len(set(ids)) != len(ids):
            raise ValueError("step ids must be unique")
        return self
