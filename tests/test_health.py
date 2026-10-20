"""Проверяем HTTP-ответы API без запуска отдельного сервера Uvicorn."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Открыть тестовый клиент: запросы идут прямо в приложение, без сети.

    Фикстура выполняется перед каждым тестом, который принимает параметр
    client, а код после yield закрывает клиент после теста.
    """
    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_ok(client: TestClient) -> None:
    """GET /health отвечает кодом 200 и ровно ожидаемым JSON."""
    response = client.get("/health")

    assert response.status_code == 200
    # Сравниваем весь словарь, чтобы заметить появление любого лишнего поля.
    assert response.json() == {"status": "ok"}


def test_health_rejects_post(client: TestClient) -> None:
    """Маршрут объявлен только для GET, поэтому POST получает 405."""
    response = client.post("/health")

    assert response.status_code == 405


def test_openapi_describes_health(client: TestClient) -> None:
    """Схема OpenAPI, по которой строится /docs, знает версию и модель ответа."""
    schema = client.get("/openapi.json").json()

    assert schema["info"]["version"] == __version__
    assert "/health" in schema["paths"]
    health_schema = schema["components"]["schemas"]["HealthResponse"]
    assert health_schema["required"] == ["status"]
