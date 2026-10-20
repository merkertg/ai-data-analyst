"""Проверяем, откуда Settings берёт значения: код, файл .env или окружение."""

from pathlib import Path

import pytest

from app.config import Settings


def test_default_app_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без переменной окружения и без .env используется значение из кода."""
    # monkeypatch меняет окружение только на время теста и затем всё вернёт.
    monkeypatch.delenv("APP_NAME", raising=False)

    # _env_file=None отключает чтение .env: локальный файл не влияет на тест.
    settings = Settings(_env_file=None)

    assert settings.app_name == "AI Data Analyst"


def test_env_file_overrides_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Строка из .env заменяет значение по умолчанию."""
    monkeypatch.delenv("APP_NAME", raising=False)
    # tmp_path — новая пустая папка для каждого теста; её удалит Pytest.
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=From dotenv\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "From dotenv"


def test_environment_variable_beats_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Переменная окружения важнее строки в .env."""
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=From dotenv\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "From environment")

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "From environment"
