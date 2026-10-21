"""Agent routes without a database: validation, configuration, OpenAPI."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.api.agents import get_settings_factory
from app.llm.config import LLMSettings
from app.main import app


def _no_database() -> Engine:
    """Any SQL in these tests is a failure."""
    raise AssertionError("the request must be rejected before SQL")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A client whose sessions fail the test if they reach the database."""
    monkeypatch.setattr("app.api.dependencies.get_engine", _no_database)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "body",
    [{}, {"question": "  "}, {"question": "x" * 2001}, {"question": "ok?", "sql": "1"}],
    ids=["missing", "blank", "too long", "extra field"],
)
def test_invalid_question_is_422(client: TestClient, body: dict[str, str]) -> None:
    """The body is checked before settings, the provider or SQL."""
    response = client.post("/api/agent/runs", json=body)

    assert response.status_code == 422


def test_openai_without_key_is_503(client: TestClient) -> None:
    """A misconfigured provider fails before any run is stored."""
    settings = LLMSettings(_env_file=None, llm_provider="openai")
    app.dependency_overrides[get_settings_factory] = lambda: lambda: settings

    response = client.post("/api/agent/runs", json={"question": "Почему?"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Check the LLM settings: provider, key, model and limits."
    }


def test_run_id_must_be_uuid(client: TestClient) -> None:
    """A non-UUID path is a validation error, not a database lookup."""
    assert client.get("/api/agent/runs/42").status_code == 422


def test_openapi_documents_agent_routes(client: TestClient) -> None:
    """/docs lists the routes with their failure answers."""
    paths = client.get("/openapi.json").json()["paths"]

    assert {"413", "502", "503", "504"} <= set(
        paths["/api/agent/runs"]["post"]["responses"]
    )
    assert "404" in paths["/api/agent/runs/{run_id}"]["get"]["responses"]
    assert "get" in paths["/api/agent/runs"]
