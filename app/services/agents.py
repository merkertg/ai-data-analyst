"""Run the agent for a question and keep the investigation history.

Completed runs and caught LLM failures are stored with their report or public
error and partial trace. Pre-run configuration errors and an unavailable
database do not produce a stored run.
"""

import time
import uuid
from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.agents.contracts import AgentProvider
from app.agents.runtime import AgentRuntime, ToolRunner, moscow_today
from app.db.models import AgentRun, AgentRunStatus
from app.llm.config import LLMSettings
from app.llm.errors import LLMError, ToolDataUnavailable


class AgentRunFailure(Exception):
    """A stored failed run; the API answers with its status and run id."""

    def __init__(self, run_id: uuid.UUID, status_code: int, detail: str) -> None:
        """Keep only public values: the id, the HTTP status and the message."""
        super().__init__(detail)
        self.run_id = run_id
        self.status_code = status_code
        self.detail = detail


def run_question(
    session: Session,
    question: str,
    provider: AgentProvider,
    run_tool: ToolRunner,
    settings: LLMSettings,
    *,
    clock: Callable[[], float] = time.monotonic,
    today: Callable[[], date] = moscow_today,
) -> AgentRun:
    """Answer a question and commit the run, also when the run fails.

    The commit happens here, not in the route: a failed run must be saved
    before the error response, and the route's session rolls back on errors.
    """
    runtime = AgentRuntime(provider, run_tool, settings, clock=clock, today=today)
    started = clock()
    try:
        outcome = runtime.run(question)
    except ToolDataUnavailable:
        # The database itself failed: there is nowhere to store the run.
        raise
    except LLMError as error:
        run = AgentRun(
            question=question,
            status=AgentRunStatus.FAILED,
            provider=provider.provider,
            model=provider.model,
            report=None,
            error={"code": error.code, "detail": error.detail},
            trace=runtime.progress.to_dict(),
            duration_ms=_elapsed_ms(clock, started),
            app_version=__version__,
        )
        session.add(run)
        session.commit()
        raise AgentRunFailure(run.id, error.status_code, error.detail) from None
    run = AgentRun(
        question=question,
        status=AgentRunStatus.COMPLETED,
        provider=outcome.provider,
        model=outcome.model,
        report=outcome.report.model_dump(mode="json"),
        error=None,
        trace=outcome.progress.to_dict(),
        duration_ms=_elapsed_ms(clock, started),
        app_version=__version__,
    )
    session.add(run)
    session.commit()
    # created_at comes from PostgreSQL now(); read it back for the response.
    session.refresh(run)
    return run


def _elapsed_ms(clock: Callable[[], float], started: float) -> int:
    """Whole milliseconds since the start; never negative."""
    return max(0, round((clock() - started) * 1000))


def get_run(session: Session, run_id: uuid.UUID) -> AgentRun | None:
    """One stored run by id, or None."""
    return session.get(AgentRun, run_id)


def list_runs(session: Session, limit: int, offset: int) -> list[AgentRun]:
    """A page of runs, newest first; id breaks ties for a stable order."""
    query = (
        select(AgentRun)
        .order_by(AgentRun.created_at.desc(), AgentRun.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(query))
