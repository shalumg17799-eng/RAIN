"""Process metrics in Prometheus text format, with no dependency. Counts and durations only."""

import threading
from collections import defaultdict

from insights.contracts.enums import EventType
from insights.contracts.events import StageEvent
from insights.contracts.record import RunRecord


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str], int] = defaultdict(int)
        self._run_ms: dict[str, list[float]] = defaultdict(list)
        self._stage_ms: dict[str, list[float]] = defaultdict(list)
        self._tokens: dict[str, int] = defaultdict(int)
        self._refines: dict[str, int] = defaultdict(int)
        self._policy: dict[tuple[str, str], int] = defaultdict(int)

    def observe_run(self, app_id: str, status: str, record: RunRecord) -> None:
        with self._lock:
            self._requests[(app_id, status)] += 1
            self._run_ms[app_id].append(float(record.duration_ms))
            self._tokens[app_id] += record.usage.total
            self._refines[app_id] += record.refine.attempt
            for step in record.trace:
                self._stage_ms[step.step_id].append(float(step.duration_ms))

    def observe_event(self, event: StageEvent) -> None:
        if (
            event.type is EventType.STAGE_FINISHED
            and event.step_id
            and event.duration_ms is not None
        ):
            with self._lock:
                pass  # stage durations are taken from the run record, which is complete

    def observe_policy(self, layer: str, decision: str) -> None:
        with self._lock:
            self._policy[(layer, decision)] += 1

    @staticmethod
    def _quantile(values: list[float], q: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
        return ordered[index]

    def _summary(self, name: str, label: str, series: dict[str, list[float]]) -> list[str]:
        lines = []
        for key, values in sorted(series.items()):
            tag = f'{label}="{key}"'
            lines.append(f"{name}_sum{{{tag}}} {sum(values):.0f}")
            lines.append(f"{name}_count{{{tag}}} {len(values)}")
            for q in (0.5, 0.95):
                lines.append(f'{name}{{{tag},quantile="{q}"}} {self._quantile(values, q):.0f}')
        return lines

    def render(self) -> str:
        with self._lock:
            lines = [
                "# HELP insights_requests_total Requests by app and response status.",
                "# TYPE insights_requests_total counter",
            ]
            for (app_id, status), n in sorted(self._requests.items()):
                lines.append(f'insights_requests_total{{app="{app_id}",status="{status}"}} {n}')
            lines += [
                "# HELP insights_run_duration_ms Run wall-clock time by app (sum/count/p50/p95).",
                "# TYPE insights_run_duration_ms summary",
                *self._summary("insights_run_duration_ms", "app", self._run_ms),
                "# HELP insights_stage_duration_ms Stage wall-clock time by step.",
                "# TYPE insights_stage_duration_ms summary",
                *self._summary("insights_stage_duration_ms", "step", self._stage_ms),
                "# HELP insights_tokens_total Model tokens by app.",
                "# TYPE insights_tokens_total counter",
                *[
                    f'insights_tokens_total{{app="{a}"}} {n}'
                    for a, n in sorted(self._tokens.items())
                ],
                "# HELP insights_refines_total Refine attempts by app.",
                "# TYPE insights_refines_total counter",
                *[
                    f'insights_refines_total{{app="{a}"}} {n}'
                    for a, n in sorted(self._refines.items())
                ],
                "# HELP insights_policy_decisions_total Policy decisions by layer and outcome.",
                "# TYPE insights_policy_decisions_total counter",
            ]
            for (layer, decision), n in sorted(self._policy.items()):
                lines.append(
                    f'insights_policy_decisions_total{{layer="{layer}",decision="{decision}"}} {n}'
                )
            return "\n".join(lines) + "\n"
