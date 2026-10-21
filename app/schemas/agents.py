"""HTTP shapes of agent questions and stored runs."""

import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.schemas import AnalysisReport
from app.db.models import AgentRun


class AgentQuestion(BaseModel):
    """A question in natural language; nothing else is accepted."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        """Trim spaces; a question of spaces only is not a question."""
        value = value.strip()
        if len(value) < 3:
            raise ValueError("question must contain at least 3 characters")
        return value


class AgentErrorOut(BaseModel):
    """The public error of a failed run."""

    code: str
    detail: str


class ToolCallOut(BaseModel):
    """A tool call the server executed, with validated arguments and result."""

    call_id: str
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


class TokenUsageOut(BaseModel):
    """Tokens reported by the provider for the whole run."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class AgentRunSummary(BaseModel):
    """A run in the history list, without its report and trace."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    status: Literal["completed", "failed"]
    provider: Literal["mock", "openai"]
    model: str
    duration_ms: int
    created_at: datetime


class AgentRunOut(AgentRunSummary):
    """A stored run: the verified report or the error, and every tool call."""

    report: AnalysisReport | None
    error: AgentErrorOut | None
    steps: int
    corrections: int
    tool_calls: list[ToolCallOut]
    usage: TokenUsageOut | None
    app_version: str

    @classmethod
    def from_run(cls, run: AgentRun) -> Self:
        """Unpack the JSONB trace column into typed fields."""
        trace = run.trace
        return cls.model_validate(
            {
                "id": run.id,
                "question": run.question,
                "status": run.status,
                "provider": run.provider,
                "model": run.model,
                "duration_ms": run.duration_ms,
                "created_at": run.created_at,
                "report": run.report,
                "error": run.error,
                "steps": trace["steps"],
                "corrections": trace["corrections"],
                "tool_calls": trace["tool_calls"],
                "usage": trace["usage"],
                "app_version": run.app_version,
            }
        )


class AgentRunList(BaseModel):
    """A page of runs, newest first."""

    items: list[AgentRunSummary]
    limit: int
    offset: int


class AgentFailureOut(BaseModel):
    """A failed run: the public message and the id of the stored trace."""

    detail: str
    run_id: uuid.UUID
