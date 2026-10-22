"""Access control with real tokens in the *_test database.

These tests are marked real_auth: the API checks the Authorization header
against api_tokens instead of using the test analyst.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from app.api import dependencies
from app.api.auth import NOT_AUTHENTICATED, agent_limiter
from app.db.models import ApiToken
from app.main import app
from app.security.service import authenticate, issue_token, revoke_token
from app.security.tokens import Role, token_hash

pytestmark = pytest.mark.real_auth
SEPTEMBER = {
    "start": "2026-09-01",
    "end": "2026-10-01",
    "compare_start": "2026-08-01",
    "compare_end": "2026-09-01",
}


@pytest.fixture
def tokens(migrated_engine: Engine) -> Iterator[Callable[[Role], str]]:
    """Issue committed tokens for the API to find; delete them afterwards."""

    def make(role: Role, **options: int) -> str:
        with Session(migrated_engine) as session:
            _, token = issue_token(session, f"test {role}", role, **options)
            session.commit()
        return token

    yield make
    with migrated_engine.begin() as connection:
        connection.execute(text("DELETE FROM api_tokens"))


@pytest.fixture
def client(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """The real dependencies, pointed at the migrated *_test database."""
    monkeypatch.setattr(dependencies, "get_engine", lambda: migrated_engine)
    with TestClient(app) as test_client:
        yield test_client


def bearer(token: str) -> dict[str, str]:
    """An Authorization header."""
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer short"},
        bearer("ida_" + "A" * 43),
    ],
    ids=["missing", "wrong scheme", "malformed", "unknown"],
)
def test_bad_tokens_get_one_answer(client: TestClient, headers: dict[str, str]) -> None:
    """Every kind of bad token: the same 401, nothing about why."""
    response = client.get("/api/metrics/revenue", params=SEPTEMBER, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": NOT_AUTHENTICATED}
    assert response.headers["www-authenticate"] == "Bearer"


def test_revoked_and_expired_tokens_stop_working(
    client: TestClient, tokens: Callable[..., str], migrated_engine: Engine
) -> None:
    """Revocation applies to the very next request."""
    token = tokens(Role.VIEWER)
    assert client.get("/api/reports", headers=bearer(token)).status_code == 200

    with Session(migrated_engine) as session:
        row = session.scalar(
            select(ApiToken).where(ApiToken.token_hash == token_hash(token))
        )
        assert row is not None
        assert revoke_token(session, row.id)
        session.commit()

    assert client.get("/api/reports", headers=bearer(token)).status_code == 401


def test_expired_token_is_rejected(db_session: Session) -> None:
    """A token past its expiry date authenticates as nobody."""
    _, token = issue_token(db_session, "short-lived", Role.ANALYST, 1)

    assert authenticate(db_session, token) is not None
    later = datetime.now(UTC) + timedelta(days=2)
    assert authenticate(db_session, token, now=later) is None


def test_viewer_reads_but_cannot_start_costly_work(
    client: TestClient, tokens: Callable[..., str]
) -> None:
    """Viewers read analytics; saving reports and asking the agent need analyst."""
    headers = bearer(tokens(Role.VIEWER))

    assert (
        client.get(
            "/api/metrics/revenue", params=SEPTEMBER, headers=headers
        ).status_code
        == 200
    )
    report = {"kind": "comparison", **SEPTEMBER}
    assert client.post("/api/reports", json=report, headers=headers).status_code == 403
    question = {"question": "Почему упала выручка?"}
    answer = client.post("/api/agent/runs", json=question, headers=headers)
    assert answer.status_code == 403
    assert answer.json() == {"detail": "This action requires the analyst role."}


def test_analyst_can_save_reports(
    client: TestClient, tokens: Callable[..., str], migrated_engine: Engine
) -> None:
    """The analyst role passes the role check and the write happens."""
    response = client.post(
        "/api/reports",
        json={"kind": "comparison", **SEPTEMBER},
        headers=bearer(tokens(Role.ANALYST)),
    )

    assert response.status_code == 201
    with migrated_engine.begin() as connection:
        connection.execute(text("DELETE FROM reports"))


def test_agent_runs_are_rate_limited_per_token(
    client: TestClient,
    tokens: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
    migrated_engine: Engine,
) -> None:
    """Over the limit: 429 with Retry-After, before any model or SQL work."""
    monkeypatch.setattr(agent_limiter, "_limit", lambda: 2)
    headers = bearer(tokens(Role.ANALYST))
    question = {"question": "Почему в сентябре упала выручка?"}

    codes = [
        client.post("/api/agent/runs", json=question, headers=headers).status_code
        for _ in range(3)
    ]

    assert codes[:2] == [201, 201]
    assert codes[2] == 429
    limited = client.post("/api/agent/runs", json=question, headers=headers)
    assert int(limited.headers["retry-after"]) >= 1
    with migrated_engine.begin() as connection:
        connection.execute(text("DELETE FROM agent_runs"))


def test_every_api_route_requires_a_token(client: TestClient) -> None:
    """No /api route is reachable anonymously; /health and docs stay open."""
    paths = client.get("/openapi.json").json()["paths"]
    api_paths = {
        path: methods for path, methods in paths.items() if path.startswith("/api")
    }
    assert len(api_paths) >= 9
    any_id = "00000000-0000-4000-8000-000000000000"
    for path, methods in api_paths.items():
        url = path.replace("{report_id}", any_id).replace("{run_id}", any_id)
        for method in methods:
            response = client.request(method.upper(), url)
            assert response.status_code == 401, (method, path)
    for open_path in ("/health", "/docs", "/openapi.json"):
        assert client.get(open_path).status_code == 200


def test_tokens_are_stored_only_as_hashes(
    db_session: Session,
) -> None:
    """The database cannot give a working token back."""
    row, token = issue_token(db_session, "auditor", Role.VIEWER)

    stored = db_session.execute(
        text("SELECT name, role, token_hash, prefix FROM api_tokens WHERE id = :id"),
        {"id": row.id},
    ).one()
    assert stored.token_hash == token_hash(token)
    assert token not in " ".join(str(value) for value in stored)
    assert len(stored.prefix) == 12 and token.startswith(stored.prefix)


def test_openapi_documents_the_bearer_scheme(client: TestClient) -> None:
    """/docs shows the token scheme and the 401, 403 and 429 answers."""
    schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["ApiToken"]["scheme"] == "bearer"
    post = schema["paths"]["/api/agent/runs"]["post"]
    assert {"401", "403", "429"} <= set(post["responses"])
