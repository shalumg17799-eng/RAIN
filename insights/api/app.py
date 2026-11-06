"""The HTTP API: POST /v1/apps/{app_id}/ask (sync or SSE), GET runs, health, readiness, metrics.

Identity comes from the Authorization header and is turned into a Principal on the server. The
response contract is `AskResponse`; rows are joined in from the request's result store when the
response is built, and only for their owner. SSE streams stage events and never rows.
"""

import json
import logging
import queue
import threading
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.responses import PlainTextResponse, StreamingResponse
from opentelemetry.sdk.trace import TracerProvider

from insights.api.auth import ApiKeys, KeyRecord, StartupError, bearer_token, principal_for
from insights.api.settings import ServerSettings
from insights.catalog.kag_neo4j import KagConfig, build_kag_provider
from insights.catalog.provider import DirectoryCatalogs
from insights.contracts.agent import AgentDef
from insights.contracts.enums import Status
from insights.contracts.events import StageEvent
from insights.contracts.principal import Principal
from insights.contracts.profile import AppProfile, ProfileError, load_app_profile
from insights.contracts.record import RunRecord
from insights.contracts.request import AskRequest
from insights.contracts.response import AskResponse, Confidence, Data, Reason
from insights.contracts.state import AnswerRecord
from insights.datasources.base import DataSourceError
from insights.datasources.provider import EnvDataSources
from insights.gateway.config import build_gateway
from insights.gateway.gateway import LLMGateway
from insights.obs.logging import configure_logging, log_event
from insights.obs.metrics import Metrics
from insights.obs.tracing import StageSpans, build_tracer_provider, trace_id_of
from insights.contracts.orchestrator import OrchestratorDef
from insights.runtime.agent import AgentError, validate_agent
from insights.runtime.engine import Runtime
from insights.runtime.hitl import HitlDecision, HitlStore
from insights.runtime.supervisor import OrchestratorError, load_pipeline, validate_orchestrator
from insights.runtime.stores import (
    FanOutAuditSink,
    InMemoryAuditSink,
    InMemoryResultStore,
    InMemoryRunStore,
    JsonlAuditSink,
    ResultNotFoundError,
)
from insights.skills_core.protocols import Services
from insights.skills_core.registry import SkillRegistry

_log = logging.getLogger("insights.api")

# Name of the OpenAPI security scheme for the bearer API key, and the per-route marker that makes
# the /docs page attach the key entered under "Authorize". Documentation only; see `authenticate`.
BEARER_SCHEME = "BearerApiKey"
BEARER_REQUIRED: dict[str, Any] = {"security": [{BEARER_SCHEME: []}]}

API_DESCRIPTION = (
    "Natural-language question in, governed SQL-backed answer out. Identity comes from the "
    "Authorization header (Bearer key), never from the body. Every response carries "
    "`confidence.calibrated`; while it is false the score is a composite of signals and NOT a "
    "probability."
)


@dataclass(frozen=True)
class ServedApp:
    profile: AppProfile
    agent: AgentDef | OrchestratorDef


class ServerState:
    """Everything built once at startup. Fail closed: any missing or invalid piece stops it."""

    def __init__(
        self,
        settings: ServerSettings,
        *,
        tracer_provider: TracerProvider | None = None,
        environ: Mapping[str, str] | None = None,
        gateway: LLMGateway | None = None,
    ) -> None:
        self.settings = settings
        env = dict(environ if environ is not None else settings.environ)
        self.keys = ApiKeys.load(settings.keys_file)
        self.registry = SkillRegistry.scan(settings.skills_dir)
        for problem in self.registry.errors:
            log_event(
                _log, logging.WARNING, "skill_isolated", path=problem.path, error=problem.error
            )
        self.apps = self._load_apps(settings.apps_dir, settings.agents_dir)
        if not self.apps:
            raise StartupError(f"no active app profile found under {settings.apps_dir}")
        # `gateway` is a test seam: tests inject the fake test double. A default run passes None and
        # builds from configuration, where the default provider is "none" (no model).
        self.gateway = gateway if gateway is not None else build_gateway(settings.gateway)
        self.memory_audit = InMemoryAuditSink()
        audit = (
            FanOutAuditSink(self.memory_audit, JsonlAuditSink(settings.audit_file))
            if settings.audit_file
            else self.memory_audit
        )
        self.results = InMemoryResultStore()
        self.runs = InMemoryRunStore()
        self.data = EnvDataSources(env)
        self.hitl = HitlStore()
        self.runtime = Runtime(
            registry=self.registry,
            gateway=self.gateway,
            audit=audit,
            results=self.results,
            runs=self.runs,
            services=Services(
                catalogs=DirectoryCatalogs(settings.apps_dir),
                kag=build_kag_provider(KagConfig.from_env(env)),
                data=self.data,
                hitl=self.hitl,
            ),
        )
        self.metrics = Metrics()
        self.tracer_provider = tracer_provider or build_tracer_provider(settings.otel_exporter)
        self.tracer = self.tracer_provider.get_tracer("insights.api")

    def _load_apps(self, apps_dir: Path, agents_dir: Path) -> dict[str, ServedApp]:
        served: dict[str, ServedApp] = {}
        for folder in (
            sorted(p for p in apps_dir.iterdir() if p.is_dir()) if apps_dir.is_dir() else []
        ):
            profile_path = folder / "app.yaml"
            if not profile_path.is_file():
                continue
            try:
                profile = load_app_profile(profile_path)
            except ProfileError as exc:
                if "stub" in str(exc):
                    log_event(_log, logging.INFO, "app_skipped_stub", app=folder.name)
                    continue
                raise StartupError(str(exc)) from exc
            if profile.id != folder.name:
                raise StartupError(
                    f"{profile_path}: profile id {profile.id!r} must match its folder"
                )
            try:
                agent = load_pipeline(agents_dir, profile.agent.name)
            except (AgentError, OrchestratorError) as exc:
                raise StartupError(f"app {profile.id}: {exc}") from exc
            if agent.version != profile.agent.version:
                raise StartupError(
                    f"app {profile.id} pins agent {profile.agent.name}@{profile.agent.version} "
                    f"but the agent file is version {agent.version}"
                )
            problems = (
                validate_orchestrator(agent, self.registry)
                if isinstance(agent, OrchestratorDef)
                else validate_agent(agent, self.registry)
            )
            if problems:
                raise StartupError(
                    f"app {profile.id}: agent {agent.name} is invalid: {'; '.join(problems)}"
                )
            served[profile.id] = ServedApp(profile, agent)
        return served

    def readiness(self) -> tuple[bool, dict[str, str]]:
        provider = self.settings.gateway.provider
        checks: dict[str, str] = {
            "keys": f"{len(self.keys)} configured",
            "apps": ", ".join(self.apps),
            # A degraded component, not a failure: the server is ready and answers data questions
            # honestly as failed / model_unavailable until a real model is configured.
            "model": "no model configured" if provider == "none" else provider,
        }
        ok = True
        for app_id, served in self.apps.items():
            try:
                self.data.adapter_for(served.profile).ping()
                checks[f"data:{app_id}"] = "ok"
            except (DataSourceError, LookupError, ValueError) as exc:
                checks[f"data:{app_id}"] = f"unavailable ({type(exc).__name__})"
                ok = False
        return ok, checks


# ---- building the response ----------------------------------------------------------------------


class RowsGoneError(LookupError):
    """The answer's rows are no longer held (they expire a few minutes after the run)."""


def build_response(
    request_id: uuid.UUID, record: RunRecord, results: Any, principal: Principal
) -> AskResponse:
    """From the stored run to the wire contract: rows joined in for their owner only."""
    if record.outcome == "failed" or not record.output:
        code = record.failure.reason.value if record.failure else "incomplete_run"
        return AskResponse(
            request_id=request_id,
            status=Status.FAILED,
            reason=Reason(code=code, message="The request could not be completed."),
            confidence=Confidence(score=0.0, calibrated=False, signals={"reason": code}),
            trace_id=record.trace_id,
        )
    answer = AnswerRecord.model_validate(record.output["answer"])
    data = None
    if answer.status is Status.ANSWERED and answer.result_ref is not None:
        try:
            stored = results.get(answer.result_ref, owner=principal.subject)
        except ResultNotFoundError as exc:
            raise RowsGoneError("the result rows are no longer available") from exc
        data = Data(
            columns=answer.columns,
            rows=stored.rows,
            row_count=len(stored.rows),
            truncated=answer.truncated,
        )
    confidence = answer.confidence or Confidence(
        score=0.0,
        calibrated=False,
        signals={"reason": answer.reason.code if answer.reason else answer.status.value},
    )
    return AskResponse(
        request_id=request_id,
        status=answer.status,
        data=data,
        query=answer.query,
        confidence=confidence,
        assumptions=answer.assumptions,
        provenance=answer.provenance,
        clarification=answer.clarification,
        refine=answer.refine,
        narrative=answer.narrative,
        reason=answer.reason,
        trace_id=record.trace_id,
    )


def _sse(event: str, payload: Mapping[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


# ---- the app ------------------------------------------------------------------------------------


def create_app(
    settings: ServerSettings,
    *,
    tracer_provider: TracerProvider | None = None,
    environ: Mapping[str, str] | None = None,
    gateway: LLMGateway | None = None,
) -> FastAPI:
    configure_logging()
    state = ServerState(settings, tracer_provider=tracer_provider, environ=environ, gateway=gateway)
    app = FastAPI(title="Insights Server", version="0.1.0", description=API_DESCRIPTION)
    app.state.insights = state

    # Documentation only: declare the bearer key in the OpenAPI document so the /docs page shows an
    # Authorize button. Authentication itself stays in `authenticate` below, which reads the header.
    def openapi_with_bearer() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title, version=app.version, description=app.description, routes=app.routes
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})[BEARER_SCHEME] = {
            "type": "http",
            "scheme": "bearer",
            "description": "API key from scripts/make_api_key.py (Authorization: Bearer <key>).",
        }
        app.openapi_schema = schema
        return schema

    app.openapi = openapi_with_bearer  # type: ignore[method-assign]

    def authenticate(request: Request) -> KeyRecord:
        record = state.keys.authenticate(bearer_token(request.headers.get("authorization")))
        if record is None:
            raise HTTPException(status_code=401, detail="a valid bearer API key is required")
        return record

    def served_app(record: KeyRecord, app_id: str) -> ServedApp:
        served = state.apps.get(app_id)
        if served is None:
            raise HTTPException(status_code=404, detail="unknown application")
        if record.apps and app_id not in record.apps:
            raise HTTPException(status_code=403, detail="this key may not call this application")
        return served

    def run_once(
        served: ServedApp, principal: Principal, body: AskRequest, sinks: list[Any], trace_id: str
    ) -> RunRecord:
        def fan_out(event: StageEvent) -> None:
            for sink in sinks:
                sink(event)

        return state.runtime.run(
            served.agent,
            input={
                "request_id": str(body.request_id),
                "query": body.query,
                "context": body.context.model_dump(exclude_none=True),
            },
            principal=principal,
            app=served.profile,
            options=body.options,
            on_event=fan_out,
            conversation_id=str(body.conversation_id) if body.conversation_id else None,
            trace_id=trace_id,
        )

    @app.post(
        "/v1/apps/{app_id}/ask",
        response_model=AskResponse,
        response_model_exclude_none=False,
        openapi_extra=BEARER_REQUIRED,
    )
    def ask(app_id: str, body: AskRequest, request: Request, response: Response) -> Any:
        record = authenticate(request)
        served = served_app(record, app_id)
        principal = principal_for(record, served.profile)

        if body.options.stream:
            return StreamingResponse(
                stream_run(served, principal, body),
                media_type="text/event-stream",
                headers={"cache-control": "no-store", "x-accel-buffering": "no"},
            )

        with state.tracer.start_as_current_span("ask", attributes={"insights.app": app_id}) as span:
            trace_id = trace_id_of(span)
            run = run_once(served, principal, body, [StageSpans(state.tracer, span)], trace_id)
            try:
                payload = build_response(body.request_id, run, state.results, principal)
            except RowsGoneError:
                raise HTTPException(
                    status_code=410, detail="the result rows have expired"
                ) from None
            span.set_attribute("insights.status", payload.status.value)
        state.metrics.observe_run(app_id, payload.status.value, run)
        response.headers["x-trace-id"] = trace_id
        return payload

    def stream_run(served: ServedApp, principal: Principal, body: AskRequest) -> Iterator[str]:
        """Stage events as they happen, then `done` with the run id. Never rows (fetch the run)."""
        events: queue.Queue[StageEvent | None] = queue.Queue()
        outcome: dict[str, Any] = {}
        # Not a context manager: a generator is resumed on different threads, and OpenTelemetry
        # refuses to detach a context token on another thread. The span is ended by hand.
        span = state.tracer.start_span("ask", attributes={"insights.app": served.profile.id})
        trace_id = trace_id_of(span)
        spans = StageSpans(state.tracer, span)

        def worker() -> None:
            try:
                outcome["run"] = run_once(served, principal, body, [events.put, spans], trace_id)
            except Exception as exc:  # reported on the stream, never swallowed
                outcome["error"] = type(exc).__name__
            finally:
                events.put(None)

        try:
            thread = threading.Thread(target=worker, name="insights-ask", daemon=True)
            thread.start()
            yield _sse("start", {"request_id": str(body.request_id), "trace_id": trace_id})
            while True:
                try:
                    event = events.get(timeout=15.0)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    break
                yield _sse("stage", event.model_dump(mode="json", exclude_none=True))
            thread.join(timeout=5)
            run = outcome.get("run")
            if run is None:
                span.set_attribute("insights.status", "error")
                yield _sse(
                    "error",
                    {"request_id": str(body.request_id), "error": outcome.get("error", "unknown")},
                )
                return
            answer = (run.output or {}).get("answer") or {}
            status = str(answer.get("status") or "failed")
            span.set_attribute("insights.status", status)
            state.metrics.observe_run(served.profile.id, status, run)
            yield _sse(
                "done",
                {
                    "request_id": str(body.request_id),
                    "run_id": run.run_id,
                    "status": status,
                    "trace_id": trace_id,
                },
            )
        finally:
            span.end()

    @app.get(
        "/v1/apps/{app_id}/runs/{run_id}",
        response_model=AskResponse,
        response_model_exclude_none=False,
        openapi_extra=BEARER_REQUIRED,
    )
    def get_run(app_id: str, run_id: str, request: Request, response: Response) -> Any:
        record = authenticate(request)
        served = served_app(record, app_id)
        principal = principal_for(record, served.profile)
        run = state.runs.get(run_id, principal)  # owner-scoped: others see "no such run"
        if run is None or run.app_id != app_id:
            raise HTTPException(status_code=404, detail="unknown run")
        try:
            request_id = uuid.UUID(run.request_id) if run.request_id else uuid.uuid4()
        except ValueError:
            request_id = uuid.uuid4()
        try:
            payload = build_response(request_id, run, state.results, principal)
        except RowsGoneError:
            raise HTTPException(status_code=410, detail="the result rows have expired") from None
        response.headers["x-trace-id"] = run.trace_id
        return payload

    # ---- human-in-the-loop review ------------------------------------------------------------

    @app.get("/v1/hitl/pending", openapi_extra=BEARER_REQUIRED)
    def hitl_pending(request: Request) -> dict[str, Any]:
        authenticate(request)
        return {
            "pending": [
                {
                    "run_id": p.run_id,
                    "trace_id": p.trace_id,
                    "reason": p.reason,
                    "question": p.question,
                    "sql": p.sql,
                    "confidence": p.confidence,
                    "proposed_narrative": p.proposed_narrative,
                    "waiting_s": p.waiting_s,
                }
                for p in state.hitl.pending()
            ]
        }

    @app.post("/v1/hitl/{run_id}", openapi_extra=BEARER_REQUIRED)
    def hitl_decide(run_id: str, body: dict[str, Any], request: Request) -> dict[str, Any]:
        record = authenticate(request)
        action = body.get("action")
        if action not in ("approve", "edit", "reject"):
            raise HTTPException(status_code=422, detail="action must be approve, edit or reject")
        try:
            decision = HitlDecision(
                action=action,
                decided_by=record.subject,
                edited_narrative=body.get("edited_narrative"),
                note=body.get("note"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not state.hitl.decide(run_id, decision):
            raise HTTPException(status_code=404, detail="no pending review for this run")
        return {"resolved": True, "run_id": run_id, "action": action}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(response: Response) -> dict[str, Any]:
        ok, checks = state.readiness()
        response.status_code = 200 if ok else 503
        return {"status": "ready" if ok else "not_ready", "checks": checks}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return state.metrics.render()

    return app
