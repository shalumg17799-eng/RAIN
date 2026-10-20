"""SKILL.md front matter (the manifest). Parsing and the registry arrive in S2."""

from typing import Annotated, Any

from pydantic import Field, StringConstraints, model_validator

from insights.contracts.common import Contract, Identifier, SemVer, SkillName

FieldName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]


class SkillValidation(Contract):
    required_input: tuple[FieldName, ...] = ()
    """Missing or null input fails the step before the skill runs."""
    required_output: tuple[FieldName, ...] = ()
    """Checked after the skill runs."""


class SkillManifest(Contract):
    name: SkillName
    version: SemVer
    description: str = Field(min_length=1)
    dependencies: tuple[SkillName, ...] = ()
    restricted: bool = False
    validation: SkillValidation = SkillValidation()
    labels: tuple[Identifier, ...] = ()
    """The closed set of labels this skill may return in `label`. Empty means it returns none."""
    examples: tuple[dict[str, Any], ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> "SkillManifest":
        if self.name in self.dependencies:
            raise ValueError("a skill cannot depend on itself")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies must be unique")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("labels must be unique")
        return self
