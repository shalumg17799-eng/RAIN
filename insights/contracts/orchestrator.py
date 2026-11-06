"""agents/<pack>/orchestrator.yaml as data: the supervisor's capability map, not a sequence.

An orchestrator names the stages its pack can fill, the input each stage's skill receives
(references over run state, exactly the `$.input / $.steps / $.refine / $.fanout` grammar the
step contract uses), fan-out, and bounds. WHICH skill fills a stage, WHEN a stage runs, and
every loop-back is decided at runtime by the supervisor from the registry's capabilities and the
run state — nothing here fixes an order beyond the stages' declared data dependencies.
"""

from typing import Any, Literal

from pydantic import Field, model_validator

from insights.contracts.agent import Ref, _check_refs
from insights.contracts.common import Contract, Identifier, SemVer, SkillName
from insights.contracts.skill import PackName


class FanoutDef(Contract):
    """Fan the stage out over a list in state: one skill run per item (LangGraph Send)."""

    over: Ref
    item_key: Identifier = "item"
    branch_key: Identifier | None = None
    """A field of each item used as the branch id in events (a persona name, a source id).
    None means the item itself (a string) is the branch id."""


class StageDef(Contract):
    stage: Identifier
    input: dict[str, Any] = Field(default_factory=dict)
    fanout: FanoutDef | None = None
    terminal: bool = False
    """The stage every run ends at (exactly one). Always eligible; runs once, last."""
    terminal_labels: tuple[Identifier, ...] = ()
    """Output labels (besides `escalate`) that send the run to the terminal stage."""

    @model_validator(mode="after")
    def _refs_are_well_formed(self) -> "StageDef":
        _check_refs(self.input, f"stage {self.stage}.input")
        if self.terminal and self.fanout is not None:
            raise ValueError(f"stage {self.stage}: the terminal stage cannot fan out")
        return self


class SupervisorLimits(Contract):
    max_refines: int = Field(ge=0, le=5)
    max_steps: int = Field(ge=2, le=64)
    """Supervisor decisions one run may take (each stage run costs one)."""
    max_tokens: int = Field(ge=1)
    deadline_ms: int = Field(ge=100)


class OrchestratorDef(Contract):
    name: SkillName
    version: SemVer
    pack: PackName
    description: str = ""
    on_refine_exhausted: Literal["terminal", "continue"] = "terminal"
    """What happens when a stage asks for one refine too many: go straight to the terminal stage
    (the PRD posture: finalize honestly), or continue forward with the imperfect artifact so the
    later gates — assessment, human review — judge it (the NLQ posture)."""
    stages: tuple[StageDef, ...] = Field(min_length=1)
    output: dict[str, Ref] = Field(min_length=1)
    limits: SupervisorLimits

    @model_validator(mode="after")
    def _shape(self) -> "OrchestratorDef":
        names = [stage.stage for stage in self.stages]
        if len(set(names)) != len(names):
            raise ValueError("stage names must be unique")
        terminals = [stage.stage for stage in self.stages if stage.terminal]
        if len(terminals) != 1:
            raise ValueError(f"exactly one terminal stage is required, found {terminals}")
        return self

    @property
    def terminal_stage(self) -> StageDef:
        return next(stage for stage in self.stages if stage.terminal)

    def stage_named(self, name: str) -> StageDef | None:
        return next((stage for stage in self.stages if stage.stage == name), None)
