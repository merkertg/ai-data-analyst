"""Проверка /ready без настоящей базы: недоступная база даёт 503 без секретов."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.db.session import DatabaseNotConfigured, create_database_engine
from app.main import NOT_READY, app, database_engine

# Порт 1 на этом компьютере закрыт: соединение отклоняется сразу.
UNREACHABLE_URL = "postgresql+psycopg://analyst:secret@127.0.0.1:1/missing_test"


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Тестовый клиент; подмены зависимостей снимаются после каждого теста."""
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_ready_without_database_url(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Без DATABASE_URL приложение работает, но /ready честно отвечает 503."""

    def not_configured() -> Engine:
        raise DatabaseNotConfigured("DATABASE_URL не задан")

    monkeypatch.setattr("app.main.get_engine", not_configured)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": NOT_READY}


def test_ready_with_unreachable_database(client: TestClient) -> None:
    """Недоступный сервер — 503, а адрес и пароль не попадают в ответ."""
    app.dependency_overrides[database_engine] = lambda: create_database_engine(
        UNREACHABLE_URL
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": NOT_READY}
    assert "secret" not in response.text


def test_health_does_not_need_database(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/health не обращается к базе: он отвечает, даже если база не настроена."""

    def not_configured() -> Engine:
        raise DatabaseNotConfigured("DATABASE_URL не задан")

    monkeypatch.setattr("app.main.get_engine", not_configured)

    assert client.get("/health").json() == {"status": "ok"}


def test_openapi_documents_ready(client: TestClient) -> None:
    """В схеме OpenAPI описаны оба ответа /ready: 200 и 503."""
    schema = client.get("/openapi.json").json()

    responses = schema["paths"]["/ready"]["get"]["responses"]
    assert {"200", "503"} <= set(responses)
