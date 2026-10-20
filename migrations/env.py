"""Запуск Alembic с адресом из настроек и поддержкой изолированных тестов."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

import app.db.models  # noqa: F401 — регистрирует все таблицы в общей metadata.
from app.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False: запуск из тестов не глушит чужие журналы.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# С этими метаданными autogenerate и alembic check сравнивают базу.
target_metadata = Base.metadata


def get_database_url() -> str:
    """Адрес из теста (config.attributes) или из настроек приложения."""
    database_url = config.attributes.get("database_url")
    if database_url is None:
        database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL не задан. Создай .env по .env.example "
            "или передай DATABASE_URL в окружении."
        )
    return str(database_url)


def run_migrations_offline() -> None:
    """Сгенерировать SQL миграций без подключения к базе (alembic upgrade --sql)."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate_with_connection(connection: Connection) -> None:
    """Применить миграции через уже открытое соединение."""
    # compare_type: alembic check заметит и изменение типа столбца.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Открыть короткое соединение и применить версионированные миграции."""
    # URL передаётся прямо в SQLAlchemy: ConfigParser не трогает % в пароле.
    engine = create_engine(get_database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            migrate_with_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
