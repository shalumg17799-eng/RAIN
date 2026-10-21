"""Load agents/<name>.yaml and validate it against the skill registry.

validate_agent checks, and reports every problem at once:
  - every skill (and pinned version) exists
  - label sets are closed and every label is mapped; nothing undeclared is mapped
  - every step is reachable
  - loops only go through `refine_*` labels; a route with a refine label also has an `escalate` exit
  - references name only steps that always run first (dominators), known refine fields, and never
    a server-side object (principal, app profile)
Limits are required by the AgentDef model itself.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from insights.contracts.agent import AgentDef, is_ref
from insights.contracts.state import RefineState
from insights.skills_core.errors import SkillNotFoundError
from insights.skills_core.registry import SkillRegistry
from insights.yamlio import load_yaml

REFINE_PREFIX = "refine_"
ESCALATE = "escalate"
SERVER_SIDE_KEYS = frozenset({"principal", "app", "app_profile", "token", "authorization"})
REFINE_FIELDS = frozenset(RefineState.model_fields)
STEP_FIELDS = frozenset({"output", "label", "skill", "version", "runs"})

Edge = tuple[str, str, str | None]  # (source step, target step, label or None for "next step")


class AgentError(ValueError):
    """The agent file is unreadable or structurally wrong."""


class AgentValidationError(ValueError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def parse_agent(text: str) -> AgentDef:
    try:
        raw = load_yaml(text)
    except (yaml.YAMLError, ValueError) as exc:
        raise AgentError(f"agent file is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise AgentError("agent file must be a mapping")
    try:
        return AgentDef.model_validate(raw)
    except ValidationError as exc:
        raise AgentError(f"invalid agent: {exc}") from exc


def load_agent(path: Path) -> AgentDef:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AgentError(f"cannot read {path}: {exc}") from exc
    try:
        return parse_agent(text)
    except AgentError as exc:
        raise AgentError(f"{path}: {exc}") from exc


# ---- graph helpers -------------------------------------------------------------------------


def _edges(agent: AgentDef) -> list[Edge]:
    known = {s.id for s in agent.steps}
    edges: list[Edge] = []
    for i, step in enumerate(agent.steps):
        if step.route is not None:
            edges += [(step.id, dst, label) for label, dst in step.route.to.items() if dst in known]
        elif i + 1 < len(agent.steps):
            edges.append((step.id, agent.steps[i + 1].id, None))
    return edges


def _reachable_and_back_edges(agent: AgentDef, edges: list[Edge]) -> tuple[set[str], set[Edge]]:
    out: dict[str, list[Edge]] = {s.id: [] for s in agent.steps}
    for edge in edges:
        out[edge[0]].append(edge)
    seen: set[str] = set()
    on_stack: set[str] = set()
    back: set[Edge] = set()

    def visit(node: str) -> None:
        seen.add(node)
        on_stack.add(node)
        for edge in out[node]:
            if edge[1] in on_stack:
                back.add(edge)
            elif edge[1] not in seen:
                visit(edge[1])
        on_stack.discard(node)

    visit(agent.steps[0].id)
    return seen, back


def _dominators(
    agent: AgentDef, edges: list[Edge], reachable: set[str], back: set[Edge]
) -> dict[str, set[str]]:
    """dom[n] = steps that run on every path from the start to n (loop back edges ignored)."""
    start = agent.steps[0].id
    preds: dict[str, list[str]] = {n: [] for n in reachable}
    for src, dst, label in edges:
        if (src, dst, label) not in back and src in reachable and dst in reachable:
            preds[dst].append(src)
    dom = {n: set(reachable) for n in reachable}
    dom[start] = {start}
    changed = True
    while changed:
        changed = False
        for step in agent.steps:
            node = step.id
            if node == start or node not in reachable:
                continue
            common = set.intersection(*(dom[p] for p in preds[node])) if preds[node] else set()
            new = {node} | common
            if new != dom[node]:
                dom[node] = new
                changed = True
    return dom


def _refs_in(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        if is_ref(value):
            yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _refs_in(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _refs_in(item)


def _check_ref(
    ref: str,
    where: str,
    *,
    must_precede: set[str] | None,
    known: set[str],
    own_id: str | None,
    map_ids: set[str] = frozenset(),
) -> list[str]:
    """Problems with one reference. `must_precede` is the dominator set of the referring point."""
    parts = ref[2:].split(".")
    root = parts[0]
    if root == "input":
        if len(parts) > 1 and parts[1] in SERVER_SIDE_KEYS:
            return [f"{where}: {ref} reaches for a server-side object; it never travels in input"]
    elif root == "refine":
        if len(parts) > 1 and parts[1] not in REFINE_FIELDS:
            return [
                f"{where}: {ref} is not a refine field (known: {', '.join(sorted(REFINE_FIELDS))})"
            ]
    elif root == "fanout":
        if len(parts) < 2 or parts[1] not in map_ids:
            return [
                f"{where}: {ref} must name a map step "
                f"(map steps: {', '.join(sorted(map_ids)) or 'none'})"
            ]
        if must_precede is not None and parts[1] not in must_precede:
            return [
                f"{where}: {ref} references map step {parts[1]!r}, which does not always run "
                "before this point"
            ]
    elif root == "steps" and len(parts) > 1:
        step_id = parts[1]
        if step_id not in known:
            return [f"{where}: {ref} names unknown step {step_id!r}"]
        if len(parts) > 2 and parts[2] not in STEP_FIELDS:
            return [f"{where}: {ref} is not a step field (known: {', '.join(sorted(STEP_FIELDS))})"]
        if step_id == own_id:
            return [f"{where}: {ref} reads the step's own output"]
        if must_precede is not None and step_id not in must_precede:
            return [
                f"{where}: {ref} references step {step_id!r}, which does not always run "
                "before this point (use $.steps for the whole container)"
            ]
    return []


# ---- validation ----------------------------------------------------------------------------


def validate_agent(agent: AgentDef, registry: SkillRegistry) -> list[str]:
    problems: list[str] = []
    known = {s.id for s in agent.steps}
    map_ids = {s.id for s in agent.steps if s.map is not None}

    for step in agent.steps:
        pin = f"@{step.version}" if step.version else ""
        try:
            loaded = registry.get(step.skill, step.version)
        except SkillNotFoundError:
            problems.append(f"step {step.id!r}: skill '{step.skill}{pin}' is not loaded")
            loaded = None
        labels = set(loaded.manifest.labels) if loaded else None

        if loaded and labels and step.route is None and step.map is None:
            problems.append(
                f"step {step.id!r}: skill {step.skill!r} declares labels {sorted(labels)} "
                "but the step has no route"
            )
        if loaded and not labels and step.route is not None:
            problems.append(
                f"step {step.id!r}: skill {step.skill!r} declares no labels "
                "but the step has a route"
            )
        if step.route is not None:
            mapped = set(step.route.to)
            if labels:
                problems += [
                    f"step {step.id!r}: label {label!r} of skill {step.skill!r} is not mapped"
                    for label in sorted(labels - mapped)
                ]
                problems += [
                    f"step {step.id!r}: route maps label {label!r} which skill "
                    f"{step.skill!r} does not declare"
                    for label in sorted(mapped - labels)
                ]
            expected = f"$.steps.{step.id}.output.label"
            if step.route.on != expected:
                problems.append(f"step {step.id!r}: route.on must be {expected!r}")
            problems += [
                f"step {step.id!r}: route target {dst!r} (label {label!r}) is not a step"
                for label, dst in step.route.to.items()
                if dst not in known
            ]
            if any(label.startswith(REFINE_PREFIX) for label in mapped) and ESCALATE not in mapped:
                problems.append(
                    f"step {step.id!r}: a route with refine labels needs an {ESCALATE!r} exit"
                )

    edges = _edges(agent)
    reachable, back = _reachable_and_back_edges(agent, edges)
    problems += [
        f"step {s.id!r} is unreachable from the first step"
        for s in agent.steps
        if s.id not in reachable
    ]
    for src, dst, label in sorted(back, key=lambda e: (e[0], e[1], e[2] or "")):
        if label is None or not label.startswith(REFINE_PREFIX):
            via = f"label {label!r}" if label else "its natural order"
            problems.append(
                f"step {src!r}: {via} loops back to {dst!r}; "
                f"only {REFINE_PREFIX}* labels may form a loop"
            )

    dom = _dominators(agent, edges, reachable, back)
    for step in agent.steps:
        if step.id not in dom:
            continue
        refs = list(_refs_in(step.input))
        if step.map is not None:
            refs.append(step.map.over)
        for ref in refs:
            problems += _check_ref(
                ref,
                f"step {step.id!r} input",
                must_precede=dom[step.id],
                known=known,
                own_id=step.id,
                map_ids=map_ids,
            )
    last = agent.steps[-1].id
    for key, ref in agent.output.items():
        problems += _check_ref(
            ref,
            f"output {key!r}",
            must_precede=dom.get(last),
            known=known,
            own_id=None,
            map_ids=map_ids,
        )
    return problems


def assert_valid_agent(agent: AgentDef, registry: SkillRegistry) -> None:
    problems = validate_agent(agent, registry)
    if problems:
        raise AgentValidationError(problems)
