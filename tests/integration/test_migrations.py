"""Миграции создают и удаляют схему, модели совпадают с базой, /ready видит версию."""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect

from app.db.readiness import expected_revision
from app.main import app, database_engine

DOMAIN_TABLES = {
    "customers",
    "products",
    "orders",
    "order_items",
    "refunds",
    "inventory_snapshots",
}
# Миграция 0002 (этап 06) добавляет сохранённые отчёты.
ALL_TABLES = DOMAIN_TABLES | {"reports", "alembic_version"}


@pytest.fixture
def ready_client(migrated_engine: Engine) -> Iterator[TestClient]:
    """Клиент API, у которого /ready смотрит в тестовую базу."""
    app.dependency_overrides[database_engine] = lambda: migrated_engine
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def table_names(engine: Engine) -> set[str]:
    """Имена таблиц схемы public в тестовой базе."""
    return set(inspect(engine).get_table_names())


def test_upgrade_creates_domain_tables(migrated_engine: Engine) -> None:
    """После upgrade head: шесть таблиц продаж, reports и alembic_version."""
    assert table_names(migrated_engine) == ALL_TABLES


def test_downgrade_and_upgrade_round_trip(
    migrated_engine: Engine, migration_config: Config
) -> None:
    """Откат удаляет все таблицы, повторный upgrade создаёт их снова."""
    command.downgrade(migration_config, "base")
    try:
        assert table_names(migrated_engine) == {"alembic_version"}
    finally:
        command.upgrade(migration_config, "head")

    assert table_names(migrated_engine) == ALL_TABLES


def test_models_match_migrations(
    migrated_engine: Engine, migration_config: Config
) -> None:
    """alembic check: в моделях нет изменений, которых нет в миграциях."""
    # Если кто-то поменял модель и забыл миграцию, check выбросит исключение.
    command.check(migration_config)


def test_ready_reports_current_revision(ready_client: TestClient) -> None:
    """На актуальной схеме /ready отвечает 200 и называет версию."""
    response = ready_client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "revision": expected_revision()}


def test_ready_rejects_outdated_schema(
    ready_client: TestClient, migration_config: Config
) -> None:
    """Пустая или отставшая схема — 503: принимать запросы ещё рано."""
    command.downgrade(migration_config, "base")
    try:
        response = ready_client.get("/ready")
    finally:
        command.upgrade(migration_config, "head")

    assert response.status_code == 503


def test_reports_migration_rolls_back_alone(
    migrated_engine: Engine, migration_config: Config
) -> None:
    """Откат 0002 удаляет только reports: таблицы продаж остаются на месте."""
    command.downgrade(migration_config, "0001")
    try:
        assert table_names(migrated_engine) == DOMAIN_TABLES | {"alembic_version"}
    finally:
        command.upgrade(migration_config, "head")

    assert table_names(migrated_engine) == ALL_TABLES
