"""OpenTelemetry tracing. Exporter chosen by env: DIF_OTLP_ENDPOINT (e.g. Jaeger/Tempo/Azure Monitor collector)
or DIF_OTEL_CONSOLE=1. With neither set, spans are no-ops (zero overhead)."""
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_done = False


def setup(service="dif-platform"):
    global _done
    if _done:
        return
    _done = True
    ep, console = os.getenv("DIF_OTLP_ENDPOINT"), os.getenv("DIF_OTEL_CONSOLE")
    if not (ep or console):
        return
    tp = TracerProvider(resource=Resource.create({"service.name": os.getenv("DIF_SERVICE_NAME", service)}))
    if ep:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=ep.rstrip("/") + "/v1/traces")))
    if console:
        tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tp)


tracer = trace.get_tracer("dif")
