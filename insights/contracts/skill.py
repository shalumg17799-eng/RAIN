"""SKILL.md front matter (the manifest). Parsing and the registry arrive in S2."""

from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from insights.contracts.common import Contract, Identifier, SemVer, SkillName

FieldName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]

PackName = Literal["insights", "data"]
"""The two independent skill packs. Nothing in one may import, call or reference the other."""

SkillKind = Literal["agentic", "guarded", "deterministic"]
"""agentic: a bounded plan->tool->observe loop drives the artifact.
guarded: an agent picks parameters and handles errors, but a deterministic core cannot be bypassed.
deterministic: no LLM at all."""


class SkillValidation(Contract):
    required_input: tuple[FieldName, ...] = ()
    """Missing or null input fails the step before the skill runs."""
    required_output: tuple[FieldName, ...] = ()
    """Checked after the skill runs."""


class Capabilities(Contract):
    """What a skill can do, for runtime selection by an orchestrator. Closed vocabulary only."""

    intents: tuple[Identifier, ...] = ()
    """Request intents this skill serves (for example `data_query`, `metadata_question`)."""
    data_sources: tuple[Identifier, ...] = ()
    """Data source types the skill can work against (for example `postgres`, `knowledge_graph`)."""
    consumes: tuple[Identifier, ...] = ()
    """Blackboard artifacts that must exist before this skill can run."""
    produces: tuple[Identifier, ...] = ()
    """Blackboard artifacts this skill contributes."""


class SkillManifest(Contract):
    name: SkillName
    version: SemVer
    description: str = Field(min_length=1)
    pack: PackName | None = None
    """Which pack the skill belongs to; must match its pack folder under skills/."""
    stage: Identifier | None = None
    """The pipeline stage this skill fills (one skill per stage may be chosen at runtime)."""
    kind: SkillKind | None = None
    capabilities: Capabilities = Capabilities()
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
