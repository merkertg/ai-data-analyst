"""/api/agent/runs: ask the AI analyst and read the investigation history."""

import uuid
from collections.abc import Callable
from functools import partial
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

from app.agents.contracts import AgentProvider
from app.agents.provider import get_agent_provider
from app.agents.tools import SessionFactory, ToolExecutor
from app.api.auth import (
    AUTH_RESPONSES,
    WRITE_RESPONSES,
    get_principal,
    limit_agent_runs,
)
from app.api.dependencies import LazySession, ReadSession, WriteSession
from app.api.errors import DATABASE_RESPONSES
from app.llm.config import LLMSettings, get_llm_settings
from app.schemas.agents import (
    AgentFailureOut,
    AgentQuestion,
    AgentRunList,
    AgentRunOut,
    AgentRunSummary,
)
from app.services import agents

# Stage 09: every route needs a valid API token (any role reads).
router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
    dependencies=[Depends(get_principal)],
    responses=AUTH_RESPONSES,
)

ProviderFactory = Callable[[LLMSettings], AgentProvider]

RUN_RESPONSES: dict[int | str, dict[str, object]] = {
    413: {"model": AgentFailureOut, "description": "Analysis context too long"},
    502: {"model": AgentFailureOut, "description": "Unusable model answer"},
    503: {"description": "Database or LLM provider unavailable or not configured"},
    504: {"model": AgentFailureOut, "description": "The run ran out of time"},
}


def get_settings_factory() -> Callable[[], LLMSettings]:
    """Settings are read inside the route, after the body is validated.

    FastAPI resolves dependencies even for invalid requests, so returning a
    factory keeps a broken .env from turning a 422 into a 503.
    """
    return get_llm_settings


def get_provider_factory() -> ProviderFactory:
    """Tests replace this with a scripted provider."""
    return get_agent_provider


def get_tool_sessions() -> SessionFactory:
    """One REPEATABLE READ READ ONLY session per tool call."""
    return partial(LazySession, read_only=True)


@router.post(
    "/runs",
    status_code=201,
    responses={**RUN_RESPONSES, **WRITE_RESPONSES},
    # A run may call a paid model: analysts only, rate limited per token.
    dependencies=[Depends(limit_agent_runs)],
)
def create_run(
    request: Annotated[AgentQuestion, Body()],
    session: WriteSession,
    response: Response,
    settings_factory: Annotated[
        Callable[[], LLMSettings], Depends(get_settings_factory)
    ],
    provider_factory: Annotated[ProviderFactory, Depends(get_provider_factory)],
    tool_sessions: Annotated[SessionFactory, Depends(get_tool_sessions)],
) -> AgentRunOut:
    """Answer a question with tools and return the verified report.

    Completed runs and caught LLM failures are stored. Failures include a run_id
    when persistence succeeds; pre-run configuration and database failures do not.
    """
    settings = settings_factory()
    provider = provider_factory(settings)
    run = agents.run_question(
        session, request.question, provider, ToolExecutor(tool_sessions), settings
    )
    response.headers["Location"] = f"/api/agent/runs/{run.id}"
    return AgentRunOut.from_run(run)


@router.get(
    "/runs/{run_id}",
    responses={404: {"description": "Agent run not found"}, **DATABASE_RESPONSES},
)
def get_run(run_id: uuid.UUID, session: ReadSession) -> AgentRunOut:
    """A stored run with its report or error and every tool call."""
    run = agents.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return AgentRunOut.from_run(run)


@router.get("/runs", responses=DATABASE_RESPONSES)
def list_runs(
    session: ReadSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AgentRunList:
    """The investigation history, newest first, without reports and traces."""
    items = agents.list_runs(session, limit, offset)
    return AgentRunList(
        items=[AgentRunSummary.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
    )
