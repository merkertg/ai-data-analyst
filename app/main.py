"""Точка входа API: создаём приложение FastAPI и служебный маршрут /health."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app import __version__
from app.config import settings

# Этот объект находит Uvicorn по адресу app.main:app, его же вызывают тесты.
# Название и версия попадают в OpenAPI-схему и на страницу /docs.
app = FastAPI(
    title=settings.app_name,
    description="AI-powered business analytics platform for IndustrialFlow",
    version=__version__,
)


class HealthResponse(BaseModel):
    """Ответ проверки живости: процесс запущен и отвечает на HTTP-запросы."""

    # Literal допускает ровно одно значение: ответ с другим FastAPI не отправит.
    status: Literal["ok"]


@app.get("/health")
def health() -> HealthResponse:
    """Сообщить, что API работает; базу данных этот маршрут не проверяет."""
    return HealthResponse(status="ok")
