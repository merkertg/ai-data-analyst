"""Единая декларативная база и предсказуемые имена ограничений."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Одинаковые имена в SQLAlchemy и Alembic: по имени ограничения из ошибки
# сразу видно таблицу и правило, а миграция может удалить его при откате.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Общие метаданные всех таблиц; таблицы создаёт только Alembic."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
