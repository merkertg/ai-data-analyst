"""The agent over HTTP on the sample: a verified report and stored history.

The demo provider answers without a network; tools read the same rolled-back
test transaction as the routes.
"""

import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, nullcontext
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.contracts import AgentTurn, ProviderName, ToolCall
from app.agents.mock import MockProvider
from app.api.agents import get_provider_factory, get_settings_factory, get_tool_sessions
from app.api.dependencies import read_session, write_session
from app.db.models import AgentRun
from app.db.sample import add_sample_data
from app.llm.config import LLMSettings
from app.main import app

SETTINGS = LLMSettings(_env_file=None, agent_max_steps=4)


class LoopingProvider:
    """A model that keeps asking for coverage and never writes a report."""

    provider: ProviderName = "mock"
    model = "looping"

    def __init__(self) -> None:
        self.turns = 0

    def next_turn(
        self, history: list[dict[str, Any]], tools: Any, remaining: float
    ) -> AgentTurn:
        self.turns += 1
        call = ToolCall(f"loop-{self.turns}", "get_data_coverage", "{}")
        item = {"type": "function_call", "call_id": call.call_id, "name": call.name}
        return AgentTurn([item | {"arguments": "{}"}], [call], None, self.model)


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """Routes and tools share the test transaction; settings ignore .env."""
    add_sample_data(db_session)

    def test_session() -> Iterator[Session]:
        yield db_session

    def tool_sessions() -> AbstractContextManager[Session]:
        return nullcontext(db_session)

    app.dependency_overrides[read_session] = test_session
    app.dependency_overrides[write_session] = test_session
    app.dependency_overrides[get_tool_sessions] = lambda: tool_sessions
    app.dependency_overrides[get_settings_factory] = lambda: lambda: SETTINGS
    app.dependency_overrides[get_provider_factory] = lambda: lambda _: MockProvider()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def evidence_values(report: dict[str, Any]) -> set[str]:
    """Every value cited by the report's facts."""
    return {item["value"] for fact in report["facts"] for item in fact["evidence"]}


def test_question_gets_a_verified_report(client: TestClient) -> None:
    """October vs September: −291 500.00 (−94.34 %), pumps −300 000.00."""
    response = client.post(
        "/api/agent/runs", json={"question": "Почему в октябре упала выручка?"}
    )

    assert response.status_code == 201
    run = response.json()
    assert response.headers["location"] == f"/api/agent/runs/{run['id']}"
    assert (run["status"], run["provider"], run["error"]) == ("completed", "mock", None)
    report = run["report"]
    assert report["language"] == "ru"
    assert {"-291500.00", "-94.34", "Насосы", "-300000.00", "102.92"} <= (
        evidence_values(report)
    )
    assert {"Северо-Запад", "-171500.00", "58.83"} <= evidence_values(report)
    assert [call["name"] for call in run["tool_calls"]][:2] == [
        "get_data_coverage",
        "compare_periods",
    ]
    assert run["steps"] == 4 and run["corrections"] == 0
    assert "Демонстрационный режим" in report["limitations"][0]


def test_run_is_stored_and_listed(client: TestClient, db_session: Session) -> None:
    """GET returns the same run; the list shows it without the report."""
    created = client.post(
        "/api/agent/runs", json={"question": "What happened in October?"}
    ).json()

    fetched = client.get(f"/api/agent/runs/{created['id']}")
    listing = client.get("/api/agent/runs", params={"limit": 5}).json()

    assert fetched.json() == created
    assert created["report"]["language"] == "en"
    assert listing["items"][0]["id"] == created["id"]
    assert "report" not in listing["items"][0]
    stored = db_session.scalar(
        select(AgentRun).where(AgentRun.id == uuid.UUID(created["id"]))
    )
    assert stored is not None and stored.trace["tool_calls"]


def test_failed_run_is_stored_with_its_trace(client: TestClient) -> None:
    """502 names the run; the stored run shows what the agent managed to do."""
    app.dependency_overrides[get_provider_factory] = lambda: lambda _: LoopingProvider()

    response = client.post("/api/agent/runs", json={"question": "Почему?"})

    assert response.status_code == 502
    body = response.json()
    assert body["detail"] == (
        "The agent reached its step limit without a verified report."
    )
    run = client.get(f"/api/agent/runs/{body['run_id']}").json()
    assert run["status"] == "failed"
    assert run["report"] is None
    assert run["error"]["code"] == "step_limit"
    assert len(run["tool_calls"]) == 4


def test_unknown_run_is_404(client: TestClient) -> None:
    """A valid but unknown UUID is 404."""
    response = client.get(f"/api/agent/runs/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Agent run not found"}


def test_database_requires_report_or_error(db_session: Session) -> None:
    """PostgreSQL rejects a completed run without a report."""
    db_session.add(
        AgentRun(
            question="Почему?",
            status="completed",
            provider="mock",
            model="x",
            report=None,
            error=None,
            trace={},
            duration_ms=1,
            app_version="0.1.0",
        )
    )

    with pytest.raises(IntegrityError, match="outcome_matches_status"):
        db_session.flush()
