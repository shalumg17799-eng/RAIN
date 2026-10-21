"""The supervisor: picks the next agent at runtime from the registry, never from a sequence.

Plain Python, no LangGraph (the graph wiring lives in insights/runtime/graph.py). The decision
function is pure — (orchestrator, registry views, run state) in, one Decision out — so every
selection rule is unit-testable without a graph, a gateway or a thread.

How a run moves:
- Forward progress: the first declared stage that is not yet done, whose consumed artifacts all
  exist, with at least one registered skill whose capabilities match the run (intent, data source
  types). Which skill fills the stage is chosen here, from the registry, and recorded with a
  typed reason and the candidates considered.
- Loop-backs: a stage output labelled `refine_<x>` jumps back to the stage that produces artifact
  `x` (or the stage named `x`, or itself for `refine_self`), invalidating everything downstream,
  bounded by max_refines; exhaustion goes to the terminal stage instead.
- Failure labels: `escalate` or a stage's declared terminal_labels go straight to the terminal
  stage, which always runs, so every run ends with an honest report or answer.
- Fan-out: a stage with `fanout` dispatches one run per item (LangGraph Send); the per-item
  outputs land in `$.fanout.<stage>` for the consuming stage to reduce.

Every decision is appended to the run state and emitted as a typed SUPERVISOR_DECISION event: the
stage, the chosen skill, a reason code from a closed set, and who else was considered.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from insights.contracts.orchestrator import OrchestratorDef, StageDef
from insights.skills_core.registry import SkillRegistry
from insights.yamlio import load_yaml

ESCALATE = "escalate"
REFINE_PREFIX = "refine_"

DecisionReason = Literal[
    "artifact_missing",     # normal forward progress: the stage's artifacts do not exist yet
    "intent_match",         # forward progress where the skill was picked for the routed intent
    "refine_requested",     # a loop-back a stage asked for, within the refine budget
    "refines_exhausted",    # a loop-back was asked for but the budget is spent -> terminal
    "escalation",           # a stage escalated or returned one of its terminal labels
    "fanout_dispatch",      # the stage fans out over a list (one Send per item)
    "pipeline_complete",    # nothing left to do -> terminal
    "goal_reached",         # the terminal stage has run -> end
    "run_failed",           # the engine recorded a failure -> end
    "max_steps",            # the supervisor's own step bound was hit -> terminal
]


class OrchestratorError(ValueError):
    """The orchestrator file is unreadable or structurally wrong."""


def load_pipeline(agents_dir: Path, name: str):
    """The definition an app pins by name: `agents/<name>.yaml` (a routed graph agent) or a
    pack's `agents/<pack>/orchestrator.yaml` whose name matches (a supervisor)."""
    flat = agents_dir / f"{name}.yaml"
    if flat.is_file():
        from insights.runtime.agent import load_agent

        return load_agent(flat)
    for orch_path in sorted(agents_dir.glob("*/orchestrator.yaml")):
        orch = load_orchestrator(orch_path)
        if orch.name == name:
            return orch
    raise OrchestratorError(
        f"no agent or orchestrator named {name!r} under {agents_dir} "
        f"(looked for {name}.yaml and */orchestrator.yaml)"
    )


def load_orchestrator(path: Path) -> OrchestratorDef:
    try:
        raw = load_yaml(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise OrchestratorError(f"{path}: cannot read orchestrator: {exc}") from exc
    if not isinstance(raw, dict):
        raise OrchestratorError(f"{path}: orchestrator must be a mapping")
    try:
        return OrchestratorDef.model_validate(raw)
    except ValidationError as exc:
        raise OrchestratorError(f"{path}: invalid orchestrator: {exc}") from exc


PLATFORM_SOURCE_TYPES = ("catalog", "knowledge_graph")
"""Source types every app has: the entitlement-filtered catalog and the KAG seam (which may be a
stub that reports itself unavailable — retrieval falls back, so selection may still offer it)."""


def source_types_for(app: Any) -> tuple[str, ...]:
    kinds = {str(ds.kind) for ds in getattr(app, "datasources", None) or ()}
    return tuple(sorted(kinds | set(PLATFORM_SOURCE_TYPES)))


# ---- what the registry offers --------------------------------------------------------------


@dataclass(frozen=True)
class SkillView:
    """The selection-relevant slice of one registered skill's manifest."""

    name: str
    version: str
    stage: str
    kind: str
    intents: tuple[str, ...]
    data_sources: tuple[str, ...]
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    labels: tuple[str, ...]


def registry_views(registry: SkillRegistry, pack: str) -> dict[str, list[SkillView]]:
    """Stage -> the pack's candidate skills, in deterministic (name) order."""
    views: dict[str, list[SkillView]] = {}
    for name in registry.names(pack):
        skill = registry.get(name)
        manifest = skill.manifest
        if manifest.stage is None:
            continue
        views.setdefault(manifest.stage, []).append(
            SkillView(
                name=manifest.name,
                version=manifest.version,
                stage=manifest.stage,
                kind=manifest.kind or "agentic",
                intents=tuple(manifest.capabilities.intents),
                data_sources=tuple(manifest.capabilities.data_sources),
                consumes=tuple(manifest.capabilities.consumes),
                produces=tuple(manifest.capabilities.produces),
                labels=tuple(manifest.labels),
            )
        )
    for candidates in views.values():
        candidates.sort(key=lambda v: v.name)
    return views


# ---- the decision ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    action: Literal["run", "fanout", "end"]
    reason: str
    stage: str | None = None
    skill: str | None = None
    considered: tuple[str, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)

    def record(self, seq: int) -> dict[str, Any]:
        return {
            "seq": seq,
            "action": self.action,
            "stage": self.stage,
            "skill": self.skill,
            "reason": self.reason,
            "considered": list(self.considered),
            "detail": self.detail,
        }


def _stage_done(state: dict[str, Any], stage: str) -> bool:
    needed = int((state.get("needed_runs") or {}).get(stage, 1))
    return int((state.get("exec_counts") or {}).get(stage, 0)) >= needed


def _ran_skill(state: dict[str, Any], stage: str) -> str | None:
    record = (state.get("steps") or {}).get(stage)
    return record.get("skill") if isinstance(record, dict) else None


def _output_of(state: dict[str, Any], stage: str) -> dict[str, Any]:
    record = (state.get("steps") or {}).get(stage) or {}
    output = record.get("output") if isinstance(record, dict) else None
    return output if isinstance(output, dict) else {}


def current_intent(state: dict[str, Any]) -> str | None:
    """The routed intent, read from whichever done stage produced one."""
    for record in (state.get("steps") or {}).values():
        output = record.get("output") if isinstance(record, dict) else None
        if isinstance(output, dict) and isinstance(output.get("intent"), str):
            return output["intent"]
    return None


def produced_artifacts(
    state: dict[str, Any], views: dict[str, list[SkillView]]
) -> set[str]:
    """Artifacts whose producing stage is done (by the skill that actually ran)."""
    artifacts: set[str] = set()
    for stage, candidates in views.items():
        if not _stage_done(state, stage):
            continue
        ran = _ran_skill(state, stage)
        for view in candidates:
            if ran is None or view.name == ran:
                artifacts.update(view.produces)
    # a fan-out stage's items are an artifact too: the reducing stage consumes $.fanout.<stage>
    for stage in state.get("fanout") or {}:
        artifacts.add(f"fanout_{stage}")
    return artifacts


def eligible_candidates(
    view_list: list[SkillView],
    *,
    intent: str | None,
    source_types: tuple[str, ...],
    artifacts: set[str],
) -> list[SkillView]:
    out = []
    for view in view_list:
        if view.intents and (intent is None or intent not in view.intents):
            continue
        if view.data_sources and source_types and not set(view.data_sources) & set(source_types):
            continue
        if any(needed not in artifacts for needed in view.consumes):
            continue
        out.append(view)
    # the most intent-specific candidate wins; names break ties (already name-sorted)
    out.sort(key=lambda v: (0 if intent and intent in v.intents else 1, v.name))
    return out


REFINE_ALIASES = {
    "query": "sql",             # refine_query re-runs whatever produces the SQL
    "ontology": "ontology_drafts",  # refine_ontology re-runs the per-persona curation fan-out
}
"""Historic refine labels whose suffix names a stage's role rather than its artifact."""


def refine_target(
    label: str, views: dict[str, list[SkillView]], own_stage: str, stages: tuple[str, ...]
) -> str | None:
    """The stage a refine_<x> label loops back to, or None when nothing matches."""
    suffix = label[len(REFINE_PREFIX):]
    if suffix == "self":
        return own_stage
    suffix = REFINE_ALIASES.get(suffix, suffix)
    for stage in stages:
        for view in views.get(stage, []):
            if suffix in view.produces:
                return stage
    return suffix if suffix in stages else None


def choose_next(
    orch: OrchestratorDef,
    views: dict[str, list[SkillView]],
    state: dict[str, Any],
    *,
    source_types: tuple[str, ...] = (),
) -> Decision:
    terminal = orch.terminal_stage
    stage_names = tuple(stage.stage for stage in orch.stages)
    decisions = state.get("decisions") or []

    if state.get("failure"):
        return Decision(action="end", reason="run_failed")
    if _stage_done(state, terminal.stage):
        return Decision(action="end", reason="goal_reached", stage=terminal.stage)

    def terminal_decision(reason: str, detail: dict[str, Any] | None = None) -> Decision:
        candidates = views.get(terminal.stage, [])
        if not candidates:
            return Decision(action="end", reason=reason, detail={"missing_terminal": True})
        return Decision(
            action="run",
            reason=reason,
            stage=terminal.stage,
            skill=candidates[0].name,
            considered=tuple(v.name for v in candidates),
            detail=detail or {},
        )

    stage_runs = sum(1 for d in decisions if d.get("action") in ("run", "fanout"))
    if stage_runs >= orch.limits.max_steps:
        return terminal_decision("max_steps", {"stage_runs": stage_runs})

    # --- react to the last stage that ran: refine loop-backs and terminal labels -------------
    last_run = next(
        (d for d in reversed(decisions) if d.get("action") in ("run", "fanout")), None
    )
    if last_run is not None and last_run.get("action") == "run":
        stage_name = last_run.get("stage")
        stage_def = orch.stage_named(stage_name) if stage_name else None
        label = _output_of(state, stage_name).get("label") if stage_name else None
        if stage_def is not None and not stage_def.terminal and isinstance(label, str):
            if label.startswith(REFINE_PREFIX):
                refine = state.get("refine") or {}
                if int(refine.get("attempt") or 0) >= int(refine.get("max_refines") or 0):
                    return terminal_decision(
                        "refines_exhausted", {"from_stage": stage_name, "label": label}
                    )
                target = refine_target(label, views, stage_name, stage_names)
                if target is not None:
                    candidates = eligible_candidates(
                        views.get(target, []),
                        intent=current_intent(state),
                        source_types=source_types,
                        artifacts=produced_artifacts(state, views),
                    )
                    if candidates:
                        target_def = orch.stage_named(target)
                        return Decision(
                            action="fanout"
                            if target_def is not None and target_def.fanout is not None
                            else "run",
                            reason="refine_requested",
                            stage=target,
                            skill=candidates[0].name,
                            considered=tuple(v.name for v in candidates),
                            detail={"from_stage": stage_name, "label": label},
                        )
                return terminal_decision(
                    "escalation", {"from_stage": stage_name, "label": label}
                )
            if label == ESCALATE or label in stage_def.terminal_labels:
                return terminal_decision(
                    "escalation", {"from_stage": stage_name, "label": label}
                )

    # --- forward progress ---------------------------------------------------------------------
    intent = current_intent(state)
    artifacts = produced_artifacts(state, views)
    for stage_def in orch.stages:
        if stage_def.terminal or _stage_done(state, stage_def.stage):
            continue
        candidates = eligible_candidates(
            views.get(stage_def.stage, []),
            intent=intent,
            source_types=source_types,
            artifacts=artifacts,
        )
        if not candidates:
            continue
        chosen = candidates[0]
        if stage_def.fanout is not None:
            return Decision(
                action="fanout",
                reason="fanout_dispatch",
                stage=stage_def.stage,
                skill=chosen.name,
                considered=tuple(v.name for v in candidates),
            )
        reason = "intent_match" if intent and intent in chosen.intents else "artifact_missing"
        return Decision(
            action="run",
            reason=reason,
            stage=stage_def.stage,
            skill=chosen.name,
            considered=tuple(v.name for v in candidates),
        )

    return terminal_decision("pipeline_complete")


def downstream_invalidation(
    orch: OrchestratorDef, state: dict[str, Any], target_stage: str
) -> dict[str, int]:
    """needed_runs patches for the target and every done stage after it, so they re-run."""
    patches: dict[str, int] = {}
    seen_target = False
    for stage in orch.stages:
        if stage.stage == target_stage:
            seen_target = True
        if not seen_target:
            continue
        if _stage_done(state, stage.stage):
            patches[stage.stage] = int(
                (state.get("exec_counts") or {}).get(stage.stage, 0)
            ) + 1
    patches.setdefault(
        target_stage, int((state.get("exec_counts") or {}).get(target_stage, 0)) + 1
    )
    return patches


# ---- validation ------------------------------------------------------------------------------


def validate_orchestrator(orch: OrchestratorDef, registry: SkillRegistry) -> list[str]:
    problems: list[str] = []
    views = registry_views(registry, orch.pack)
    stage_names = tuple(stage.stage for stage in orch.stages)

    for stage in orch.stages:
        candidates = views.get(stage.stage, [])
        if not candidates:
            problems.append(
                f"stage {stage.stage!r}: no {orch.pack!r}-pack skill declares this stage"
            )
            continue
        for view in candidates:
            for label in view.labels:
                if label.startswith(REFINE_PREFIX):
                    target = refine_target(label, views, stage.stage, stage_names)
                    if target is None:
                        problems.append(
                            f"stage {stage.stage!r}: skill {view.name!r} may return "
                            f"{label!r} but no stage produces that artifact"
                        )
    terminal_candidates = views.get(orch.terminal_stage.stage, [])
    if not terminal_candidates:
        problems.append(f"terminal stage {orch.terminal_stage.stage!r} has no skill")
    return problems


def assert_valid_orchestrator(orch: OrchestratorDef, registry: SkillRegistry) -> None:
    problems = validate_orchestrator(orch, registry)
    if problems:
        raise OrchestratorError("; ".join(problems))
