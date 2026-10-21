"""API input checks without a database: bad requests stop before any SQL."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.db.session import DatabaseNotConfigured
from app.main import NOT_READY, app


def _no_database() -> Engine:
    """Stand-in for get_engine: any SQL in these tests is a failure."""
    raise AssertionError("validation must reject the request before SQL")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Client whose sessions fail the test if they ever reach the database.

    Sessions resolve the engine lazily, so a request rejected with 422 must
    never call get_engine — not even to check DATABASE_URL.
    """
    monkeypatch.setattr("app.api.dependencies.get_engine", _no_database)
    with TestClient(app) as test_client:
        yield test_client


SEPTEMBER = {"start": "2026-09-01", "end": "2026-10-01"}
AUGUST = {"compare_start": "2026-08-01", "compare_end": "2026-09-01"}


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/metrics/revenue", {"start": "2026-10-01", "end": "2026-09-01"}),
        ("/api/metrics/revenue", {"start": "2026-09-01", "end": "2026-09-01"}),
        ("/api/metrics/revenue", {"start": "2026-09-01"}),
        ("/api/metrics/revenue", {"start": "2026-13-01", "end": "2026-10-01"}),
        ("/api/metrics/revenue", {"start": "2016-01-01", "end": "2026-10-01"}),
        ("/api/metrics/revenue", {**SEPTEMBER, "compare_start": "2026-08-01"}),
        ("/api/metrics/orders", {**SEPTEMBER, "unknown": "1"}),
        ("/api/analytics/categories", SEPTEMBER),
        (
            "/api/analytics/regions",
            {**SEPTEMBER, **AUGUST, "compare_end": "2026-07-01"},
        ),
        ("/api/analytics/anomalies", {**SEPTEMBER, "seed": "-1"}),
        ("/api/analytics/anomalies", {**SEPTEMBER, "seed": str(2**32)}),
    ],
    ids=[
        "reversed",
        "empty",
        "missing end",
        "not a date",
        "over 120 months",
        "half comparison",
        "unknown parameter",
        "comparison required",
        "reversed comparison",
        "negative seed",
        "seed too large",
    ],
)
def test_invalid_query_is_422(
    client: TestClient, path: str, params: dict[str, str]
) -> None:
    """Invalid periods and parameters get 422 with field details, not 500."""
    response = client.get(path, params=params)

    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "forecast", **SEPTEMBER},
        {"kind": "comparison", **SEPTEMBER},
        {"kind": "comparison", **SEPTEMBER, **AUGUST, "dimension": "product"},
        {"kind": "anomalies", "start": "2026-10-01", "end": "2026-01-01"},
        {"kind": "anomalies", **SEPTEMBER, "sql": "DROP TABLE orders"},
    ],
    ids=["unknown kind", "no comparison", "bad dimension", "reversed", "extra field"],
)
def test_invalid_report_request_is_422(
    client: TestClient, body: dict[str, str]
) -> None:
    """The discriminated request model rejects unknown kinds and extra fields."""
    response = client.post("/api/reports", json=body)

    assert response.status_code == 422


def test_report_id_must_be_uuid(client: TestClient) -> None:
    """A non-UUID path is a validation error, not a database lookup."""
    assert client.get("/api/reports/42").status_code == 422


def test_missing_database_url_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without DATABASE_URL analytics routes answer 503 without details."""

    def not_configured() -> Engine:
        raise DatabaseNotConfigured("DATABASE_URL не задан")

    monkeypatch.setattr("app.api.dependencies.get_engine", not_configured)
    with TestClient(app) as test_client:
        response = test_client.get("/api/metrics/revenue", params=SEPTEMBER)

    assert response.status_code == 503
    assert response.json() == {"detail": NOT_READY}


def test_openapi_lists_stage_06_routes(client: TestClient) -> None:
    """/docs documents every analytics route with its 503 answer."""
    paths = client.get("/openapi.json").json()["paths"]

    expected = {
        "/api/metrics/revenue": "get",
        "/api/metrics/orders": "get",
        "/api/analytics/categories": "get",
        "/api/analytics/regions": "get",
        "/api/analytics/anomalies": "get",
        "/api/reports": "post",
        "/api/reports/{report_id}": "get",
    }
    for path, method in expected.items():
        assert "503" in paths[path][method]["responses"], path
    assert "404" in paths["/api/reports/{report_id}"]["get"]["responses"]
