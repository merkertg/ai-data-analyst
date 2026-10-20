"""Настройки приложения из переменных окружения и локального файла .env."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
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
