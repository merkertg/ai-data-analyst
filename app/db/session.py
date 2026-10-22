"""Ленивое подключение к PostgreSQL и сессии с явными транзакциями."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import get_settings


class DatabaseNotConfigured(RuntimeError):
    """DATABASE_URL не задан; текст ошибки не содержит адреса и пароля."""


def create_database_engine(
    database_url: str, statement_timeout_ms: int = 15_000
) -> Engine:
    """Создать пул соединений; настоящее соединение откроет первый запрос.

    pool_pre_ping проверяет соединение из пула перед выдачей: после
    перезапуска PostgreSQL приложение не получит «мёртвое» соединение.
    connect_timeout ограничивает ожидание недоступного сервера тремя секундами.
    statement_timeout (этап 09) задаётся при подключении: PostgreSQL сама
    прерывает любой запрос этого соединения, который выполняется дольше.
    """
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 3,
            "options": f"-c statement_timeout={int(statement_timeout_ms)}",
        },
    )


@lru_cache
def get_engine() -> Engine:
    """Один пул на процесс; импорт приложения и /health не требуют базы."""
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfigured("DATABASE_URL не задан")
    return create_database_engine(
        settings.database_url, settings.database_statement_timeout_ms
    )


def get_session() -> Iterator[Session]:
    """Выдать сессию, откатить её при ошибке и всегда вернуть соединение в пул.

    Код, который пишет данные, сам вызывает session.commit(), когда все его
    действия успешны. Скрытого commit после каждого запроса нет: незавершённую
    транзакцию Session.close() откатывает.
    """
    with Session(get_engine()) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def dispose_engine() -> None:
    """Закрыть пул при остановке приложения, не создавая новый."""
    # Если базу ни разу не вызывали, пул вообще не создавался.
    if get_engine.cache_info().currsize:
        get_engine().dispose()
        get_engine.cache_clear()
