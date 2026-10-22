"""Container connection components preserve raw passwords without URL ambiguity."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config import Settings

COMPONENTS = {
    "DATABASE_HOST": "db",
    "DATABASE_NAME": "industrialflow_test",
    "DATABASE_USER": "analyst",
    "DATABASE_PASSWORD": "fixture-only",
}


@pytest.fixture(autouse=True)
def clean_database_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the user's local connection configuration outside these unit tests."""
    for name in ["DATABASE_URL", "DATABASE_PORT", *COMPONENTS]:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    "password",
    [
        "fixture@one",
        "fixture/two",
        "fixture#three",
        "fixture%four",
        "a:b?&= +",
        "тест@5",
    ],
)
def test_raw_password_is_preserved(
    password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """URL construction must not reinterpret credentials as host, path or query."""
    for key, value in COMPONENTS.items():
        monkeypatch.setenv(key, password if key == "DATABASE_PASSWORD" else value)
    settings = Settings(_env_file=None)
    assert settings.database_url is not None
    url = make_url(settings.database_url)

    assert url.password == password
    assert url.host == "db"
    assert url.database == "industrialflow_test"
    assert url.username == "analyst"
    assert url.port == 5432
    assert password not in repr(settings)


@pytest.mark.parametrize("missing", list(COMPONENTS))
def test_partial_components_fail_without_revealing_password(
    missing: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial configuration cannot silently use a different database."""
    for key, value in COMPONENTS.items():
        if key != missing:
            monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert "fixture-only" not in str(error.value)


def test_explicit_url_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing local and test DATABASE_URL workflows remain compatible."""
    for key, value in COMPONENTS.items():
        monkeypatch.setenv(key, value)
    explicit = "postgresql+psycopg://analyst:fixture@localhost:5437/explicit_test"
    monkeypatch.setenv("DATABASE_URL", explicit)

    assert Settings(_env_file=None).database_url == explicit


def test_components_from_dotenv_and_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Environment overrides a component from dotenv before URL construction."""
    source = tmp_path / ".env"
    source.write_text("\n".join(f"{key}={value}" for key, value in COMPONENTS.items()))
    monkeypatch.setenv("DATABASE_PORT", "5438")
    settings = Settings(_env_file=source)

    assert settings.database_url is not None
    assert make_url(settings.database_url).port == 5438


def test_compose_passes_raw_components_to_all_database_services() -> None:
    """The shared Compose environment must leave URL escaping to Settings."""
    compose = (Path(__file__).resolve().parents[1] / "compose.yaml").read_text()
    section = compose.split("environment: &database-environment", 1)[1].split(
        "services:", 1
    )[0]

    assert "DATABASE_URL:" not in section
    assert "DATABASE_PASSWORD: ${POSTGRES_PASSWORD:-local-development-only}" in section
    assert "DATABASE_HOST: db" in section
