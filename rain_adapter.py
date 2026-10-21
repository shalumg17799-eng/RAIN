"""RAIN FastAPI Adapter Router.

Bridges RAIN's existing FastAPI application and frontend body-based persona requests
to the Insights Server governed runtime engine.

Usage in RAIN's main.py:
    from fastapi import FastAPI
    from insights.api.rain_adapter import get_rain_router

    app = FastAPI()
    app.include_router(get_rain_router(), prefix="/api/v2")
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import uuid
from typing import Any
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from insights.api.auth import bearer_token, principal_for
from insights.api.settings import ServerSettings
from insights.api.app import ServerState, build_response, RowsGoneError
from insights.contracts.request import AskRequest, AskContext
from insights.contracts.response import AskResponse
from insights.config import environment
from insights.cli import repo_root

_log = logging.getLogger("insights.rain_adapter")
_stage_log = logging.getLogger("insights.stages")


def _console_event(event) -> None:
    """One console line per engine stage event, so the terminal shows the agent's
    route -> sliver/metadata -> generate -> execute -> assess -> compose progress live.
    Best effort by design: the emitter logs and swallows any sink failure."""
    kind = event.type.value
    if kind == "stage_started":
        _stage_log.info("  >> %-15s %s (attempt %d)", event.step_id, event.skill, event.attempt or 0)
    elif kind == "stage_finished":
        tokens = event.tokens.total if event.tokens else 0
        _stage_log.info(
            "  << %-15s label=%-20s %5d ms  %4d tokens",
            event.step_id, event.label, event.duration_ms or 0, tokens,
        )
    elif kind == "refine":
        _stage_log.info("  ~~ refine #%d requested by %s (%s)", event.attempt or 0, event.step_id, event.label)
    elif kind == "progress":
        suffix = f"={event.count}" if event.count is not None else ""
        _stage_log.info("   .. %-15s %s%s", event.step_id, event.note, suffix)
    elif kind == "run_finished":
        tokens = event.tokens.total if event.tokens else 0
        failure = f" ({event.failure_reason.value})" if event.failure_reason else ""
        _stage_log.info(
            "  == run %s %s in %d ms, %d tokens%s",
            event.run_id[:8], event.outcome, event.duration_ms or 0, tokens, failure,
        )


class RainAskPayload(BaseModel):
    query: str
    persona: str = Field(default="executive", description="RAIN persona (e.g. executive, loan_officer)")
    market: str | None = "finance"
    product: str | None = "rain"
    stream: bool = False
    conversation_id: str | None = None

_server_state: ServerState | None = None


def _run_once(state: ServerState, served, principal, body: AskRequest, trace_id: str, on_event=_console_event):
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
        on_event=on_event,
        conversation_id=str(body.conversation_id) if body.conversation_id else None,
        trace_id=trace_id,
    )


def _sse(kind: str, data: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"


def _stream_run(state: ServerState, served, principal, body: AskRequest, trace_id: str, request_id) -> StreamingResponse:
    """SSE: one `stage` event per engine StageEvent (the same ones printed to the
    console), then one final `result` event carrying the usual AskResponse JSON.
    Stage events never carry rows (enforced by the engine's contracts)."""
    events: queue.Queue = queue.Queue()

    def sink(event) -> None:
        _console_event(event)  # the terminal keeps its stage view too
        events.put(("stage", event.model_dump(mode="json")))

    def work() -> None:
        try:
            run = _run_once(state, served, principal, body, trace_id, on_event=sink)
            res = build_response(request_id, run, state.results, principal)
            events.put(("result", res.model_dump(mode="json")))
        except RowsGoneError:
            events.put(("error", {"detail": "Result rows expired"}))
        except Exception as exc:  # surfaced to the client as an SSE error event
            _log.exception("streamed run failed")
            events.put(("error", {"detail": type(exc).__name__}))
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def gen():
        while True:
            item = events.get()
            if item is None:
                break
            yield _sse(*item)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"x-trace-id": trace_id, "Cache-Control": "no-cache"},
    )


def get_or_create_state(settings: ServerSettings | None = None) -> ServerState:
    global _server_state
    if _server_state is not None:
        return _server_state

    if settings is None:
        root = repo_root()
        env_path = root / ".env"
        if not env_path.is_file():
            env_path = root / "rain-api" / ".env"
        environ = environment(env_path)
        aliases = {
            "INSIGHTS_PG_HOST": "PG_HOST",
            "INSIGHTS_PG_PORT": "PG_PORT",
            "INSIGHTS_KAG_URI": "NEO4J_URI",
            "INSIGHTS_KAG_USER": "NEO4J_USER",
            "INSIGHTS_KAG_PASSWORD": "NEO4J_PASSWORD",
            "INSIGHTS_KAG_DATABASE": "NEO4J_DATABASE",
        }
        for target, source in aliases.items():
            if not environ.get(target) and environ.get(source):
                environ[target] = environ[source]
        keys_file = Path(environ.get("INSIGHTS_API_KEYS_FILE", "apps/keys.local.yaml"))
        if not keys_file.is_absolute():
            keys_file = root / keys_file
        environ["INSIGHTS_API_KEYS_FILE"] = str(keys_file)
        settings = ServerSettings.from_env(environ)

    _server_state = ServerState(settings)
    return _server_state


def get_rain_router(settings: ServerSettings | None = None) -> APIRouter:
    router = APIRouter(tags=["Insights Intelligence Layer"])
    state = get_or_create_state(settings)

    @router.post("/ask", response_model=AskResponse)
    def ask_rain(payload: RainAskPayload, request: Request, response: Response) -> Any:
        app_id = "rain"
        record = state.keys.authenticate(bearer_token(request.headers.get("authorization")))
        if record is None:
            raise HTTPException(status_code=401, detail="a valid bearer API key is required")
        if record.apps and app_id not in record.apps:
            raise HTTPException(status_code=403, detail="this key may not call this application")

        served = state.apps.get(app_id)
        if served is None:
            raise HTTPException(status_code=404, detail=f"Application '{app_id}' not found under apps/.")

        # Validate persona
        persona = payload.persona.lower().strip()
        if persona not in served.profile.roles or persona not in record.roles:
            raise HTTPException(
                status_code=403, 
                detail="the authenticated key is not entitled to the requested persona",
            )

        principal = principal_for(record, served.profile)

        request_id = uuid.uuid4()
        body = AskRequest(
            request_id=request_id,
            query=payload.query,
            context=AskContext(market=payload.market, product=payload.product),
            conversation_id=uuid.UUID(payload.conversation_id) if payload.conversation_id else None,
        )

        trace_id = uuid.uuid4().hex
        _stage_log.info("== ASK persona=%s trace=%s stream=%s q=%.80r", persona, trace_id[:8], payload.stream, payload.query)
        if payload.stream:
            return _stream_run(state, served, principal, body, trace_id, request_id)
        run = _run_once(state, served, principal, body, trace_id)

        try:
            res = build_response(request_id, run, state.results, principal)
        except RowsGoneError:
            raise HTTPException(status_code=410, detail="Result rows expired")

        response.headers["x-trace-id"] = trace_id
        return res

    # ---- human-in-the-loop review (the chat UI's approve / edit / reject panel) --------------

    def _authenticated(request: Request):
        record = state.keys.authenticate(bearer_token(request.headers.get("authorization")))
        if record is None:
            raise HTTPException(status_code=401, detail="a valid bearer API key is required")
        return record

    @router.get("/hitl/pending")
    def hitl_pending(request: Request) -> dict[str, Any]:
        _authenticated(request)
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

    class HitlDecisionPayload(BaseModel):
        action: str
        edited_narrative: str | None = None
        note: str | None = None

    @router.post("/hitl/{run_id}")
    def hitl_decide(run_id: str, payload: HitlDecisionPayload, request: Request) -> dict[str, Any]:
        from insights.runtime.hitl import HitlDecision

        record = _authenticated(request)
        if payload.action not in ("approve", "edit", "reject"):
            raise HTTPException(status_code=422, detail="action must be approve, edit or reject")
        try:
            decision = HitlDecision(
                action=payload.action,
                decided_by=record.subject,
                edited_narrative=payload.edited_narrative,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not state.hitl.decide(run_id, decision):
            raise HTTPException(status_code=404, detail="no pending review for this run")
        _stage_log.info("== HITL %s run=%s by=%s", payload.action, run_id[:8], record.subject)
        return {"resolved": True, "run_id": run_id, "action": payload.action}

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "rain_insights_adapter"}

    return router
