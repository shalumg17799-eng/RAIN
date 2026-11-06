"""Evaluation metrics over per-case outcomes. Pure functions; the runner collects the outcomes."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    split: str
    expected_status: str
    expected_intent: str | None
    gold_tables: tuple[str, ...]
    status: str
    intent: str | None
    router_layer: str | None
    sliver_tables: tuple[str, ...]
    result_match: bool | None
    """None when no result-set comparison applies (a non-answer was expected or produced)."""
    confidence: float | None
    calibrated: bool
    refine_attempts: int
    tokens: int
    duration_ms: int
    stage_ms: dict[str, int] = field(default_factory=dict)
    note: str = ""
    reason_ok: bool | None = None
    """None when the case expects no reason code; otherwise whether the answer carried it."""

    @property
    def correct(self) -> bool:
        """The case passed: the right status, the right result set, the expected reason code."""
        if self.status != self.expected_status:
            return False
        return self.result_match is not False and self.reason_ok is not False


def execution_accuracy(outcomes: Sequence[CaseOutcome]) -> float | None:
    answered = [o for o in outcomes if o.expected_status == "answered"]
    if not answered:
        return None
    return sum(1 for o in answered if o.status == "answered" and o.result_match) / len(answered)


def status_accuracy(outcomes: Sequence[CaseOutcome]) -> float | None:
    if not outcomes:
        return None
    return sum(1 for o in outcomes if o.correct) / len(outcomes)


def router_accuracy(outcomes: Sequence[CaseOutcome]) -> float | None:
    routed = [o for o in outcomes if o.expected_intent is not None]
    if not routed:
        return None
    return sum(1 for o in routed if o.intent == o.expected_intent) / len(routed)


def router_layers(outcomes: Sequence[CaseOutcome]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for o in outcomes:
        if o.router_layer:
            counts[o.router_layer] = counts.get(o.router_layer, 0) + 1
    return dict(sorted(counts.items()))


def sliver_recall(outcomes: Sequence[CaseOutcome]) -> tuple[float | None, float | None]:
    """(mean per-case recall, share of cases with every gold table in the sliver: recall@k)."""
    cases = [o for o in outcomes if o.gold_tables]
    if not cases:
        return None, None
    per_case = [len(set(o.gold_tables) & set(o.sliver_tables)) / len(o.gold_tables) for o in cases]
    return sum(per_case) / len(per_case), sum(1 for r in per_case if r == 1.0) / len(per_case)


def abstain_precision(outcomes: Sequence[CaseOutcome]) -> float | None:
    """Of the abstentions, the share that were right to abstain (an answer was not expected)."""
    abstained = [o for o in outcomes if o.status == "abstained"]
    if not abstained:
        return None
    return sum(1 for o in abstained if o.expected_status != "answered") / len(abstained)


def calibration_error(outcomes: Sequence[CaseOutcome], bins: int = 5) -> float | None:
    """ECE over answered runs: |mean confidence - accuracy| per bin, weighted by bin size."""
    answered = [
        o
        for o in outcomes
        if o.status == "answered" and o.confidence is not None and o.result_match is not None
    ]
    if not answered:
        return None
    buckets: dict[int, list[CaseOutcome]] = {}
    for o in answered:
        index = min(bins - 1, int((o.confidence or 0.0) * bins))
        buckets.setdefault(index, []).append(o)
    error = 0.0
    for members in buckets.values():
        mean_confidence = sum(o.confidence or 0.0 for o in members) / len(members)
        accuracy = sum(1 for o in members if o.result_match) / len(members)
        error += abs(mean_confidence - accuracy) * len(members) / len(answered)
    return error


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return float(ordered[index])


def latency(outcomes: Sequence[CaseOutcome]) -> dict[str, dict[str, float]]:
    """p50 and p95 for the run and for every stage, in milliseconds."""
    out = {
        "run": {
            "p50": percentile([o.duration_ms for o in outcomes], 0.5),
            "p95": percentile([o.duration_ms for o in outcomes], 0.95),
        }
    }
    stages: dict[str, list[float]] = {}
    for o in outcomes:
        for step, ms in o.stage_ms.items():
            stages.setdefault(step, []).append(float(ms))
    for step, values in sorted(stages.items()):
        out[step] = {"p50": percentile(values, 0.5), "p95": percentile(values, 0.95)}
    return out


def refine_lift(
    with_refines: Sequence[CaseOutcome], without: Sequence[CaseOutcome]
) -> float | None:
    a, b = execution_accuracy(with_refines), execution_accuracy(without)
    if a is None or b is None:
        return None
    return a - b


def summarize(outcomes: Sequence[CaseOutcome]) -> dict[str, Any]:
    recall_mean, recall_at_k = sliver_recall(outcomes)
    return {
        "cases": len(outcomes),
        "passed": sum(1 for o in outcomes if o.correct),
        "status_accuracy": status_accuracy(outcomes),
        "execution_accuracy": execution_accuracy(outcomes),
        "router_accuracy": router_accuracy(outcomes),
        "router_layers": router_layers(outcomes),
        "sliver_recall_mean": recall_mean,
        "sliver_recall_at_k": recall_at_k,
        "abstain_precision": abstain_precision(outcomes),
        "calibration_error": calibration_error(outcomes),
        "calibrated": any(o.calibrated for o in outcomes),
        "tokens_total": sum(o.tokens for o in outcomes),
        "refine_attempts_total": sum(o.refine_attempts for o in outcomes),
        "latency_ms": latency(outcomes),
    }
