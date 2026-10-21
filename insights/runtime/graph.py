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
from insights.runtime.agent import assert_valid_agent
from insights.runtime.scope import RunScope
from insights.runtime.steps import (
    execute_map_item,
    execute_step,
    failure_patch,
    map_items_and_input,
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


class GraphCache:
    """Compile once per (agent, version). A changed definition must come with a new version."""

    def __init__(self) -> None:
        self._compiled: dict[tuple[str, str], tuple[str, CompiledAgent]] = {}
        self._lock = threading.Lock()
        self.compile_count = 0

    def get(self, agent: AgentDef, registry: SkillRegistry) -> CompiledAgent:
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
            assert_valid_agent(agent, registry)
            compiled = build_graph(agent)
            self._compiled[key] = (digest, compiled)
            self.compile_count += 1
            return compiled
