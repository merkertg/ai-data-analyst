"""Точка входа API: приложение FastAPI, проверки /health и /ready, маршруты /api."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.api import analytics, metrics, reports
from app.api.errors import NOT_READY, register_error_handlers
from app.config import get_settings
from app.db.readiness import current_revision, expected_revision
from app.db.session import DatabaseNotConfigured, dispose_engine, get_engine

__all__ = ["NOT_READY", "app"]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Код до yield выполняется при старте сервера, после — при остановке.

    Пул соединений создаётся лениво при первом запросе к базе, а при
    остановке закрывается, чтобы PostgreSQL не держал брошенные соединения.
    """
    yield
    dispose_engine()


# Этот объект находит Uvicorn по адресу app.main:app, его же вызывают тесты.
# Название и версия попадают в OpenAPI-схему и на страницу /docs.
app = FastAPI(
    title=get_settings().app_name,
    description="AI-powered business analytics platform for IndustrialFlow",
    version=__version__,
    lifespan=lifespan,
)
# Недоступная база — 503 с одним и тем же текстом для всех маршрутов /api.
register_error_handlers(app)
# Этап 06: метрики, аналитика и сохранённые отчёты.
app.include_router(metrics.router)
app.include_router(analytics.router)
app.include_router(reports.router)


class HealthResponse(BaseModel):
    """Ответ проверки живости: процесс запущен и отвечает на HTTP-запросы."""

    # Literal допускает ровно одно значение: ответ с другим FastAPI не отправит.
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    """Ответ проверки готовности: база доступна, схема совпадает с кодом."""

    status: Literal["ready"]
    # Версия схемы Alembic, которую ожидает этот код и которая есть в базе.
    revision: str


def database_engine() -> Engine:
    """Зависимость /ready: пул соединений или 503, если база не настроена.

    Отдельная функция нужна тестам: app.dependency_overrides подменяет её
    пулом тестовой базы, не трогая настройки и .env разработчика.
    """
    try:
        return get_engine()
    except DatabaseNotConfigured:
        raise HTTPException(status_code=503, detail=NOT_READY) from None


@app.get("/health")
def health() -> HealthResponse:
    """Сообщить, что API работает; базу данных этот маршрут не проверяет."""
    return HealthResponse(status="ok")


@app.get(
    "/ready",
    responses={503: {"description": "Database unavailable or schema outdated"}},
)
def ready(engine: Annotated[Engine, Depends(database_engine)]) -> ReadyResponse:
    """Проверить PostgreSQL и применённые миграции перед приёмом запросов.

    /health отвечает «процесс жив». /ready дополнительно подключается к базе
    и сравнивает версию схемы в alembic_version с последней миграцией кода.
    Недоступная, пустая или устаревшая база получает 503; схема не меняется.
    """
    try:
        revision = current_revision(engine)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail=NOT_READY) from None
    if revision is None or revision != expected_revision():
        raise HTTPException(status_code=503, detail=NOT_READY)
    return ReadyResponse(status="ready", revision=revision)
