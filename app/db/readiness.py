"""Готовность базы: соединение работает и схема совпадает с миграциями кода."""

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def expected_revision() -> str:
    """Последняя версия схемы (head) из файлов migrations/versions.

    У проекта одна линия миграций, поэтому head ровно один.
    """
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise RuntimeError("В migrations/versions нет ни одной миграции")
    return head


def current_revision(engine: Engine) -> str | None:
    """Версия схемы, записанная Alembic в таблицу alembic_version.

    Если миграции ещё не применялись, таблицы нет — возвращаем None.
    Ошибки соединения передаются вызывающему коду.
    """
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        ).scalar_one()
        if not exists:
            return None
        return connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
