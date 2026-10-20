"""Пул соединений создаётся лениво и без базы ничего не ломает."""

from collections.abc import Iterator

import pytest

from app.config import Settings
from app.db import session as db_session
from app.db.session import (
    DatabaseNotConfigured,
    create_database_engine,
    dispose_engine,
    get_engine,
)


@pytest.fixture(autouse=True)
def clean_engine_cache() -> Iterator[None]:
    """Каждый тест начинает и заканчивает без закешированного пула."""
    get_engine.cache_clear()
    yield
    get_engine.cache_clear()


def test_get_engine_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без адреса get_engine сообщает понятную ошибку без подробностей."""
    monkeypatch.setattr(
        db_session, "get_settings", lambda: Settings(_env_file=None, database_url=None)
    )

    with pytest.raises(DatabaseNotConfigured):
        get_engine()


def test_engine_creation_does_not_connect() -> None:
    """create_engine только готовит пул: соединение откроет первый запрос."""
    engine = create_database_engine(
        "postgresql+psycopg://analyst:secret@127.0.0.1:1/missing_test"
    )

    assert engine.url.database == "missing_test"
    # Пароль скрыт в строковом представлении адреса.
    assert "secret" not in str(engine.url)
    engine.dispose()


def test_dispose_without_engine_is_noop() -> None:
    """Если базу не вызывали, остановка приложения не создаёт новый пул."""
    dispose_engine()

    assert get_engine.cache_info().currsize == 0
