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

import logging
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

class RainAskPayload(BaseModel):
    query: str
    persona: str = Field(default="executive", description="RAIN persona (e.g. executive, loan_officer)")
    market: str | None = "finance"
    product: str | None = "rain"
    stream: bool = False
    conversation_id: str | None = None

_server_state: ServerState | None = None


def _run_once(state: ServerState, served, principal, body: AskRequest, trace_id: str):
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
        conversation_id=str(body.conversation_id) if body.conversation_id else None,
        trace_id=trace_id,
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
        run = _run_once(state, served, principal, body, trace_id)

        try:
            res = build_response(request_id, run, state.results, principal)
        except RowsGoneError:
            raise HTTPException(status_code=410, detail="Result rows expired")

        response.headers["x-trace-id"] = trace_id
        return res

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "rain_insights_adapter"}

    return router
