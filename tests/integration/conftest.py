"""Интеграционные проверки запускаются только на явно выбранной базе *_test.

Локально без TEST_DATABASE_URL эти тесты пропускаются (pytest покажет skip),
в GitHub Actions отсутствие адреса — ошибка: CI не должен молча их терять.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Пометить все тесты этой папки маркером integration (pytest -m integration)."""
    for item in items:
        if "tests/integration" in str(item.path).replace(os.sep, "/"):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Адрес тестовой базы: только из TEST_DATABASE_URL и только с суффиксом _test.

    DATABASE_URL и .env намеренно не используются: там может быть база
    разработчика, а эти тесты удаляют и создают схему заново.
    """
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        message = "Укажи TEST_DATABASE_URL для отдельной PostgreSQL-базы *_test"
        if os.environ.get("CI", "").lower() in {"1", "true", "yes"}:
            pytest.fail(message)
        pytest.skip(message)
    database = make_url(value).database
    if not database or not database.endswith("_test"):
        pytest.fail("Интеграционные тесты разрешены только для базы с суффиксом _test")
    return value


@pytest.fixture(scope="session")
def test_engine(test_database_url: str) -> Iterator[Engine]:
    """Отдельный пул тестовой базы; закрывается после всех тестов."""
    engine = create_engine(
        test_database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3}
    )
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def migration_config(test_database_url: str) -> Config:
    """Настройки Alembic с адресом тестовой базы, без изменения .env."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    # attributes, а не set_main_option: ConfigParser не трогает % в пароле.
    config.attributes["database_url"] = test_database_url
    return config


@pytest.fixture(scope="session")
def migrated_engine(test_engine: Engine, migration_config: Config) -> Iterator[Engine]:
    """Один раз на прогон: схема с нуля только через миграции Alembic.

    create_all здесь намеренно нет: тесты должны доказать, что базу можно
    создать штатными миграциями — так же, как это сделает пользователь.
    """
    command.downgrade(migration_config, "base")
    command.upgrade(migration_config, "head")
    try:
        yield test_engine
    finally:
        command.downgrade(migration_config, "base")


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """Сессия внутри транзакции, которая откатывается после теста.

    join_transaction_mode="create_savepoint": commit и rollback внутри теста
    работают с точкой сохранения, а внешняя транзакция всё равно откатывается.
    Поэтому тесты не видят данных друг друга и не требуют очистки таблиц.
    """
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
