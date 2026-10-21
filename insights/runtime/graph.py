"""LangGraph boundary (ADR-001). This is the only module that imports LangGraph.

One graph per (agent, version), compiled once and cached. Edges follow labels: a step with a route
sends the run to the target mapped to the label it returned; a step without one flows to the next
step in the list; the last step ends the run. Per-run objects arrive through the config, so the
compiled graph is safe to share across requests and principals.
"""

import hashlib
import operator
import os
import sqlite3
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from insights.contracts.agent import AgentDef, Step
from insights.contracts.enums import EventType
from insights.contracts.events import StageEvent
from insights.contracts.orchestrator import OrchestratorDef, StageDef
from insights.runtime.agent import assert_valid_agent
from insights.runtime.scope import RunScope
from insights.runtime.steps import (
    execute_map_item,
    execute_step,
    failure_patch,
    map_items_and_input,
)
from insights.runtime.supervisor import (
    Decision,
    assert_valid_orchestrator,
    choose_next,
    downstream_invalidation,
    registry_views,
)
from insights.skills_core.registry import SkillRegistry


def _merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {**left, **right}


def _merge_fanout(
    left: dict[str, list[Any]], right: dict[str, list[Any]]
) -> dict[str, list[Any]]:
    """Append-only per map step: entries carry their dispatch `attempt`, and reducers read only
    the highest attempt, so a refine loop that re-dispatches a map never mixes passes."""
    out = {key: list(value) for key, value in (left or {}).items()}
    for key, value in (right or {}).items():
        out.setdefault(key, []).extend(value)
    return out


class GraphState(TypedDict, total=False):
    input: dict[str, Any]
    steps: Annotated[dict[str, Any], _merge]
    exec_counts: Annotated[dict[str, int], _merge]
    refine: dict[str, Any]
    trace: Annotated[list[dict[str, Any]], operator.add]
    fanout: Annotated[dict[str, list[Any]], _merge_fanout]
    failure: dict[str, Any] | None


class SupervisorState(GraphState, total=False):
    decisions: Annotated[list[dict[str, Any]], operator.add]
    needed_runs: Annotated[dict[str, int], _merge]
    """Stage -> the exec count it must reach to count as done (refine jumps bump it)."""


class AgentChangedError(RuntimeError):
    """The same (name, version) was presented with different content."""


class TracingEgressError(RuntimeError):
    """A third-party tracing flag is on, which could send questions and outputs off the system."""


_TRACING_FLAGS = ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING")
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def assert_no_third_party_tracing(environ: Mapping[str, str] | None = None) -> None:
    """LangGraph ships with LangSmith, which exports traces when these flags are set.

    Run data must stay inside the system, so the runtime refuses to build a graph while any of
    them is on. Our own tracing (OpenTelemetry, S10) is configured separately.
    """
    env = os.environ if environ is None else environ
    on = [name for name in _TRACING_FLAGS if env.get(name, "").strip().lower() in _TRUTHY]
    if on:
        raise TracingEgressError(
            f"third-party tracing is enabled ({', '.join(on)}); unset it before starting"
        )


@dataclass(frozen=True)
class Execution:
    state: dict[str, Any]
    recursion_limit_hit: bool = False
    error: Exception | None = None


class CompiledAgent:
    def __init__(self, graph: Any) -> None:
        self._graph = graph

    def execute(
        self,
        initial: dict[str, Any] | None,
        scope: RunScope,
        recursion_limit: int,
        *,
        resume: bool = False,
    ) -> Execution:
        """Run to completion. Keeps the last state seen so a failure still has its trace.

        With `resume=True` (requires a checkpointer and the original thread_id) the graph
        continues from its last checkpoint instead of starting over."""
        last = initial or {}
        config = {
            "configurable": {"scope": scope, "thread_id": scope.thread_id},
            "recursion_limit": recursion_limit,
        }
        try:
            stream_input = None if resume else initial
            for values in self._graph.stream(stream_input, config=config, stream_mode="values"):
                last = values
        except GraphRecursionError:
            return Execution(last, recursion_limit_hit=True)
        except Exception as exc:
            return Execution(last, error=exc)
        return Execution(last)


def _node(step: Step):
    def run_step(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        scope: RunScope = config["configurable"]["scope"]
        return execute_step(step, dict(state), scope)

    return run_step


def _map_anchor(step: Step):
    """The map step's own node: bounds checks and the dispatch count. Items run via Send."""

    def run_anchor(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        scope: RunScope = config["configurable"]["scope"]
        if state.get("failure"):
            return {}
        if scope.deadline.expired():
            from insights.contracts.enums import RunFailureReason

            return failure_patch(
                RunFailureReason.DEADLINE, step.id, "deadline reached before the map step"
            )
        resolved = map_items_and_input(step, dict(state), scope)
        if isinstance(resolved, dict):  # a failure patch
            return resolved
        attempt = state.get("exec_counts", {}).get(step.id, 0)
        return {"exec_counts": {step.id: attempt + 1}}

    return run_anchor


def _map_dispatch(step: Step, item_node: str, next_id: str | None):
    """Conditional-edge router: one Send per item, or straight to the next step on failure."""

    def dispatch(state: GraphState, config: RunnableConfig):
        scope: RunScope = config["configurable"]["scope"]
        if state.get("failure"):
            return END
        resolved = map_items_and_input(step, dict(state), scope)
        if isinstance(resolved, dict):
            return next_id or END
        items, base_input = resolved
        attempt = state.get("exec_counts", {}).get(step.id, 1)
        return [
            Send(
                item_node,
                {
                    "attempt": attempt,
                    "index": index,
                    "item": item,
                    "input": {**base_input, step.map.item_key: item},  # type: ignore[union-attr]
                },
            )
            for index, item in enumerate(items)
        ]

    return dispatch


def _map_item(step: Step):
    def run_item(payload: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        scope: RunScope = config["configurable"]["scope"]
        return execute_map_item(step, dict(payload), scope)

    return run_item


def _router(step: Step, next_id: str | None):
    def route(state: GraphState) -> str:
        if state.get("failure"):
            return END
        if step.route is None:
            return next_id or END
        return step.route.to[state["steps"][step.id]["label"]]

    return route


def sqlite_checkpointer(path: Path) -> Any:
    """A SQLite checkpointer at `path` (kept here: this module alone imports LangGraph).

    The database holds every superstep's full graph state — for a PRD run that includes the
    document and all draft artifacts — so it lives under the run's artifacts folder (gitignored)
    and is deleted on successful completion; the caller's retention policy prunes the rest."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    return SqliteSaver(connection)


def build_graph(agent: AgentDef, *, checkpointer: Any = None) -> CompiledAgent:
    graph = StateGraph(GraphState)
    for step in agent.steps:
        if step.map is None:
            graph.add_node(step.id, _node(step))
        else:
            graph.add_node(step.id, _map_anchor(step))
            graph.add_node(f"{step.id}__item", _map_item(step))
    graph.add_edge(START, agent.steps[0].id)
    for i, step in enumerate(agent.steps):
        next_id = agent.steps[i + 1].id if i + 1 < len(agent.steps) else None
        if step.map is not None:
            item_node = f"{step.id}__item"
            graph.add_conditional_edges(step.id, _map_dispatch(step, item_node, next_id))
            graph.add_edge(item_node, next_id or END)
            continue
        targets = set(step.route.to.values()) if step.route else ({next_id} if next_id else set())
        path_map = {target: target for target in targets} | {END: END}
        graph.add_conditional_edges(step.id, _router(step, next_id), path_map)
    return CompiledAgent(graph.compile(checkpointer=checkpointer))


# ---- supervisor graphs (one per pack orchestrator) -----------------------------------------

SUPERVISOR = "supervisor"


def _source_types(scope: RunScope) -> tuple[str, ...]:
    from insights.runtime.supervisor import source_types_for

    return source_types_for(scope.app)


def _output_of(state: dict[str, Any], stage: str) -> dict[str, Any]:
    record = (state.get("steps") or {}).get(stage) or {}
    output = record.get("output") if isinstance(record, dict) else None
    return output if isinstance(output, dict) else {}


def _supervisor_node(orch: OrchestratorDef, views: dict[str, list[Any]]):
    def run_supervisor(state: SupervisorState, config: RunnableConfig) -> dict[str, Any]:
        scope: RunScope = config["configurable"]["scope"]
        seq = len(state.get("decisions") or []) + 1
        if not state.get("failure") and scope.deadline.expired():
            from insights.contracts.enums import RunFailureReason

            return {
                **failure_patch(RunFailureReason.DEADLINE, SUPERVISOR, "deadline reached"),
                "decisions": [Decision(action="end", reason="run_failed").record(seq)],
            }
        decision = choose_next(orch, views, dict(state), source_types=_source_types(scope))
        patch: dict[str, Any] = {"decisions": [decision.record(seq)]}
        if decision.action != "end":
            scope.emitter.emit(
                StageEvent(
                    type=EventType.SUPERVISOR_DECISION,
                    run_id=scope.run_id,
                    trace_id=scope.trace_id,
                    ts=scope.now(),
                    step_id=SUPERVISOR,
                    skill=decision.skill,
                    stage=decision.stage,
                    reason=decision.reason,
                    considered=decision.considered,
                    count=seq,
                )
            )
        if decision.reason == "refine_requested":
            from_stage = str(decision.detail.get("from_stage"))
            critique = _output_of(dict(state), from_stage).get("critique")
            refine = dict(state["refine"])
            refine["attempt"] = int(refine.get("attempt") or 0) + 1
            refine["critique"] = critique
            refine["history"] = [
                *refine.get("history", []),
                {
                    "attempt": refine["attempt"],
                    "step_id": from_stage,
                    "label": decision.detail.get("label"),
                    "critique": critique,
                },
            ]
            patch["refine"] = refine
            patch["needed_runs"] = downstream_invalidation(orch, dict(state), str(decision.stage))
            scope.emitter.emit(
                StageEvent(
                    type=EventType.REFINE,
                    run_id=scope.run_id,
                    trace_id=scope.trace_id,
                    ts=scope.now(),
                    step_id=from_stage,
                    attempt=refine["attempt"],
                    label=str(decision.detail.get("label")),
                )
            )
        elif decision.reason == "refines_exhausted":
            refine = dict(state["refine"])
            refine["exhausted"] = True
            patch["refine"] = refine
        return patch

    return run_supervisor


def _supervisor_router(fanout_stages: set[str]):
    def route(state: SupervisorState):
        decisions = state.get("decisions") or []
        decision = decisions[-1] if decisions else {}
        if decision.get("action") == "end" or not decision.get("stage"):
            return END
        return str(decision["stage"])

    return route


def _sup_stage_node(stage: StageDef):
    def run_stage(state: SupervisorState, config: RunnableConfig) -> dict[str, Any]:
        scope: RunScope = config["configurable"]["scope"]
        decision = (state.get("decisions") or [{}])[-1]
        step = Step(id=stage.stage, skill=str(decision["skill"]), input=stage.input)
        return execute_step(step, dict(state), scope)

    return run_stage


def _sup_fanout_step(stage: StageDef, skill: str) -> Step:
    from insights.contracts.agent import MapSpec

    return Step(
        id=stage.stage,
        skill=skill,
        input=stage.input,
        map=MapSpec(over=stage.fanout.over, item_key=stage.fanout.item_key),  # type: ignore[union-attr]
    )


def _sup_fanout_anchor(stage: StageDef):
    def run_anchor(state: SupervisorState, config: RunnableConfig) -> dict[str, Any]:
        scope: RunScope = config["configurable"]["scope"]
        if state.get("failure"):
            return {}
        if scope.deadline.expired():
            from insights.contracts.enums import RunFailureReason

            return failure_patch(
                RunFailureReason.DEADLINE, stage.stage, "deadline reached before the fan-out"
            )
        decision = (state.get("decisions") or [{}])[-1]
        step = _sup_fanout_step(stage, str(decision["skill"]))
        resolved = map_items_and_input(step, dict(state), scope)
        if isinstance(resolved, dict):
            return resolved
        attempt = state.get("exec_counts", {}).get(stage.stage, 0)
        return {"exec_counts": {stage.stage: attempt + 1}}

    return run_anchor


def _sup_fanout_dispatch(stage: StageDef, item_node: str):
    def dispatch(state: SupervisorState, config: RunnableConfig):
        scope: RunScope = config["configurable"]["scope"]
        if state.get("failure"):
            return SUPERVISOR
        decision = (state.get("decisions") or [{}])[-1]
        step = _sup_fanout_step(stage, str(decision["skill"]))
        resolved = map_items_and_input(step, dict(state), scope)
        if isinstance(resolved, dict):
            return SUPERVISOR
        items, base_input = resolved
        attempt = state.get("exec_counts", {}).get(stage.stage, 1)
        branch_key = stage.fanout.branch_key  # type: ignore[union-attr]

        def branch_of(item: Any) -> str | None:
            if branch_key and isinstance(item, dict):
                value = item.get(branch_key)
                return str(value) if value is not None else None
            return str(item) if isinstance(item, str) else None

        return [
            Send(
                item_node,
                {
                    "attempt": attempt,
                    "index": index,
                    "item": item,
                    "skill": str(decision["skill"]),
                    "branch": branch_of(item),
                    "input": {**base_input, stage.fanout.item_key: item},  # type: ignore[union-attr]
                },
            )
            for index, item in enumerate(items)
        ]

    return dispatch


def _sup_map_item(stage: StageDef):
    def run_item(payload: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        scope: RunScope = config["configurable"]["scope"]
        step = Step(id=stage.stage, skill=str(payload.get("skill")), input={})
        return execute_map_item(step, dict(payload), scope)

    return run_item


def build_supervisor_graph(
    orch: OrchestratorDef, registry: SkillRegistry, *, checkpointer: Any = None
) -> CompiledAgent:
    views = registry_views(registry, orch.pack)
    graph = StateGraph(SupervisorState)
    fanout_stages = {stage.stage for stage in orch.stages if stage.fanout is not None}
    graph.add_node(SUPERVISOR, _supervisor_node(orch, views))
    for stage in orch.stages:
        if stage.fanout is None:
            graph.add_node(stage.stage, _sup_stage_node(stage))
            graph.add_edge(stage.stage, SUPERVISOR)
        else:
            item_node = f"{stage.stage}__item"
            graph.add_node(stage.stage, _sup_fanout_anchor(stage))
            graph.add_node(item_node, _sup_map_item(stage))
            graph.add_conditional_edges(stage.stage, _sup_fanout_dispatch(stage, item_node))
            graph.add_edge(item_node, SUPERVISOR)
    graph.add_edge(START, SUPERVISOR)
    path_map = {stage.stage: stage.stage for stage in orch.stages} | {END: END}
    graph.add_conditional_edges(SUPERVISOR, _supervisor_router(fanout_stages), path_map)
    return CompiledAgent(graph.compile(checkpointer=checkpointer))


class GraphCache:
    """Compile once per (agent, version). A changed definition must come with a new version."""

    def __init__(self) -> None:
        self._compiled: dict[tuple[str, str], tuple[str, CompiledAgent]] = {}
        self._lock = threading.Lock()
        self.compile_count = 0

    def get(self, agent: AgentDef | OrchestratorDef, registry: SkillRegistry) -> CompiledAgent:
        assert_no_third_party_tracing()  # every call: a later flag cannot slip past the cache
        key = (agent.name, agent.version)
        digest = hashlib.sha256(agent.model_dump_json().encode("utf-8")).hexdigest()
        with self._lock:
            cached = self._compiled.get(key)
            if cached is not None:
                if cached[0] != digest:
                    raise AgentChangedError(
                        f"agent {agent.name}@{agent.version} changed without a version bump; "
                        "bump the version so runs stay reproducible"
                    )
                return cached[1]
            if isinstance(agent, OrchestratorDef):
                assert_valid_orchestrator(agent, registry)
                compiled = build_supervisor_graph(agent, registry)
            else:
                assert_valid_agent(agent, registry)
                compiled = build_graph(agent)
            self._compiled[key] = (digest, compiled)
            self.compile_count += 1
            return compiled
