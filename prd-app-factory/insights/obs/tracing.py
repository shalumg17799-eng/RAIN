"""OpenTelemetry: one span per request and one child span per stage, sharing the run's trace id.

Spans carry step, skill, label, attempt, duration and token counts. Never a question, SQL or rows.
Nothing is exported unless `INSIGHTS_OTEL_EXPORTER=console` (or a provider is injected in tests).
"""

from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Span, SpanKind

from insights.contracts.enums import EventType
from insights.contracts.events import StageEvent


def build_tracer_provider(exporter: str = "none") -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({"service.name": "insights-server"}))
    if exporter == "console":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    return provider


def trace_id_of(span: Span) -> str:
    return format(span.get_span_context().trace_id, "032x")


class StageSpans:
    """An event sink that opens a child span at stage_started and closes it at stage_finished."""

    def __init__(self, tracer: trace.Tracer, parent: Span) -> None:
        self._tracer = tracer
        self._context = trace.set_span_in_context(parent)
        self._open: dict[tuple[str, int], Span] = {}

    def __call__(self, event: StageEvent) -> None:
        key = (event.step_id or "", event.attempt or 0)
        if event.type is EventType.STAGE_STARTED:
            span = self._tracer.start_span(
                f"stage {event.step_id}",
                context=self._context,
                kind=SpanKind.INTERNAL,
                attributes={
                    "insights.step": event.step_id or "",
                    "insights.skill": event.skill or "",
                    "insights.skill_version": event.skill_version or "",
                    "insights.attempt": event.attempt or 0,
                },
            )
            self._open[key] = span
        elif event.type is EventType.STAGE_FINISHED:
            span = self._open.pop(key, None)
            if span is None:
                return
            attributes: dict[str, Any] = {
                "insights.label": event.label or "",
                "insights.duration_ms": event.duration_ms or 0,
            }
            if event.tokens is not None:
                attributes["insights.tokens"] = event.tokens.total
            span.set_attributes(attributes)
            span.end()
        elif event.type is EventType.RUN_FINISHED:
            for span in self._open.values():  # a run that failed mid-stage
                span.end()
            self._open.clear()
