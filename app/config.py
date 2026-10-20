"""Настройки приложения из переменных окружения и локального файла .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация, которая читается при создании объекта настроек.

    Приоритет источников: переменная окружения → строка в .env → значение
    по умолчанию ниже. Регистр имён не важен: поле app_name читается из
    переменной APP_NAME.
    """

    # extra="ignore": позже в .env появятся ключи Docker и PostgreSQL,
    # которые к этим настройкам не относятся; без него Pydantic отклонил бы их.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Название сервиса в OpenAPI-схеме и на странице /docs.
    app_name: str = "AI Data Analyst"


# Один экземпляр на процесс: модули импортируют уже прочитанные настройки.
settings = Settings()
