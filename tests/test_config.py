"""Проверяем, откуда Settings берёт значения и как проверяется адрес базы."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

VALID_URL = "postgresql+psycopg://analyst:secret@127.0.0.1:5436/industrialflow"


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


def test_database_url_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без DATABASE_URL приложение стартует: /health не нуждается в базе."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url is None


def test_database_url_accepts_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Адрес с драйвером postgresql+psycopg и именем базы принимается как есть."""
    monkeypatch.setenv("DATABASE_URL", VALID_URL)

    settings = Settings(_env_file=None)

    assert settings.database_url == VALID_URL


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://analyst:secret@127.0.0.1:5436/industrialflow",
        "sqlite:///industrialflow.db",
        "postgresql+psycopg://analyst:secret@127.0.0.1:5436",
        "not a url",
    ],
)
def test_database_url_rejects_other_drivers_and_missing_database(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Другой драйвер, адрес без базы и мусор отклоняются при старте."""
    monkeypatch.setenv("DATABASE_URL", url)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    # hide_input_in_errors: пароль из адреса не попадает в текст ошибки.
    assert "secret" not in str(error.value)


def test_database_url_is_hidden_from_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """repr(settings) не показывает адрес с паролем: его могут записать в журнал."""
    monkeypatch.setenv("DATABASE_URL", VALID_URL)

    settings = Settings(_env_file=None)

    assert "secret" not in repr(settings)
