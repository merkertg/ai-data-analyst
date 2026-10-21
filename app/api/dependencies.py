"""Database sessions injected into routes with FastAPI Depends.

A route declares what it needs (ReadSession or WriteSession); FastAPI opens it
before the route runs and closes it afterwards. Tests replace these functions
through app.dependency_overrides with a session of the *_test database.
"""

from collections.abc import Generator
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session

from app.db.session import get_engine


class LazySession(Session):
    """A session that picks its engine at the first SQL statement.

    FastAPI resolves dependencies even when query validation fails. With an
    ordinary session an invalid request (422) would still check DATABASE_URL
    and could answer 503. Here nothing touches the database until a route
    actually runs a query.
    """

    def __init__(self, *, read_only: bool) -> None:
        """Remember whether this session must be a read-only snapshot."""
        super().__init__()
        self.read_only = read_only
        self._resolved_engine: Engine | None = None

    def get_bind(
        self,
        mapper: Any = None,
        *,
        clause: Any = None,
        bind: Any = None,
        _sa_skip_events: bool | None = None,
        _sa_skip_for_implicit_returning: bool = False,
        **kw: Any,
    ) -> Engine | Connection:
        """Resolve the configured engine; read-only sessions get a snapshot."""
        if self._resolved_engine is None:
            engine = get_engine()
            # Session caches its connection by bind identity. A new OptionEngine
            # for each statement would open multiple connections and snapshots.
            self._resolved_engine = (
                engine.execution_options(
                    isolation_level="REPEATABLE READ", postgresql_readonly=True
                )
                if self.read_only
                else engine
            )
        return self._resolved_engine


def read_session() -> Generator[Session]:
    """One read-only REPEATABLE READ snapshot per request."""
    with LazySession(read_only=True) as session:
        yield session


def write_session() -> Generator[Session]:
    """A writable session; the route commits explicitly, errors roll back."""
    with LazySession(read_only=False) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


ReadSession = Annotated[Session, Depends(read_session)]
WriteSession = Annotated[Session, Depends(write_session)]
