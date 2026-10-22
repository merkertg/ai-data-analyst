"""Настройки приложения из переменных окружения и локального файла .env."""

from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

# Единственный поддерживаемый драйвер: psycopg 3 через SQLAlchemy.
DATABASE_DRIVER = "postgresql+psycopg"


class Settings(BaseSettings):
    """Конфигурация, которая читается при создании объекта настроек.

    Приоритет источников: переменная окружения → строка в .env → значение
    по умолчанию ниже. Регистр имён не важен: поле app_name читается из
    переменной APP_NAME.
    """

    # extra="ignore": в .env лежат и ключи Docker (POSTGRES_*), которые
    # к этим настройкам не относятся; без него Pydantic отклонил бы их.
    # hide_input_in_errors: адрес БД содержит пароль — его нельзя выводить
    # в тексте ошибки проверки.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    # Название сервиса в OpenAPI-схеме и на странице /docs.
    app_name: str = "AI Data Analyst"
    # Адрес PostgreSQL. None допустим: /health работает и без базы,
    # а /ready сообщает, что приложение ещё не готово. repr=False не даёт
    # паролю попасть в print(settings) и в журналы.
    database_url: str | None = Field(default=None, repr=False)
    # Compose passes raw components so reserved password characters are safe.
    database_host: str | None = None
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str | None = None
    database_user: str | None = None
    database_password: SecretStr | None = Field(default=None, repr=False)
    # Этап 09: любой SQL-запрос приложения дольше этого времени PostgreSQL
    # прерывает сама — тяжёлый запрос не займёт базу надолго.
    database_statement_timeout_ms: int = Field(default=15_000, ge=100, le=600_000)
    # Лимиты частоты на один токен: запуск агента и сохранение отчёта
    # стоят дороже чтения (модель, детектор аномалий).
    agent_runs_per_minute: int = Field(default=6, ge=1, le=600)
    reports_per_minute: int = Field(default=30, ge=1, le=600)

    @model_validator(mode="after")
    def resolve_database_components(self) -> Self:
        """Build a correctly escaped URL when no explicit DATABASE_URL is set."""
        if self.database_url is not None:
            return self
        parts = (
            self.database_host,
            self.database_name,
            self.database_user,
            self.database_password,
        )
        if all(value is None for value in parts):
            return self
        if (
            any(value is None for value in parts)
            or not self.database_host
            or not self.database_name
            or not self.database_user
            or self.database_password is None
            or not self.database_password.get_secret_value()
        ):
            raise ValueError("Database connection components must all be provided")
        self.database_url = URL.create(
            DATABASE_DRIVER,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            username=self.database_user,
            password=self.database_password.get_secret_value(),
        ).render_as_string(hide_password=False)
        return self

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str | None) -> str | None:
        """Разрешить только psycopg 3 и явно указанное имя базы данных."""
        if value is None:
            return None
        try:
            url = make_url(value)
        except ArgumentError:
            raise ValueError("DATABASE_URL не является адресом SQLAlchemy") from None
        if url.drivername != DATABASE_DRIVER:
            raise ValueError(f"DATABASE_URL должен начинаться с {DATABASE_DRIVER}://")
        if not url.database:
            raise ValueError("В DATABASE_URL не указано имя базы данных")
        return value


@lru_cache
def get_settings() -> Settings:
    """Прочитать настройки один раз на процесс и дальше отдавать тот же объект.

    Функция вместо глобального объекта: настройки читаются при первом
    обращении, а тесты могут сбросить кеш через get_settings.cache_clear().
    """
    return Settings()
