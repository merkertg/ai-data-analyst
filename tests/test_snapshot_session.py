"""One lazy session must keep one stable bind and one connection per transaction."""

from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import QueuePool

from app.api import dependencies


@pytest.mark.parametrize("read_only", [True, False])
def test_multiple_statements_share_one_connection(
    monkeypatch: pytest.MonkeyPatch, read_only: bool
) -> None:
    """A one-connection pool exposes accidental re-checkout without PostgreSQL.

    SQLite only substitutes for transport here: PostgreSQL-specific options
    are captured and checked, while each call still creates a real OptionEngine.
    The old implementation exhausted this pool on its second statement.
    """
    engine = create_engine(
        "sqlite://", poolclass=QueuePool, pool_size=1, max_overflow=0, pool_timeout=0.05
    )
    original_options = engine.execution_options
    configured_options: list[dict[str, Any]] = []
    engine_resolutions: list[Engine] = []

    def options(**values: Any) -> Engine:
        """Record PostgreSQL settings without asking SQLite to interpret them."""
        configured_options.append(values)
        return original_options()

    def resolve_engine() -> Engine:
        """Prove that even engine selection remains lazy and happens only once."""
        engine_resolutions.append(engine)
        return engine

    monkeypatch.setattr(engine, "execution_options", options)
    monkeypatch.setattr(dependencies, "get_engine", resolve_engine)
    try:
        with dependencies.LazySession(read_only=read_only) as session:
            assert not engine_resolutions
            assert [session.scalar(text("SELECT 1")) for _ in range(3)] == [1, 1, 1]
            assert session.get_bind() is session.get_bind()
        assert engine_resolutions == [engine]
        assert configured_options == (
            [{"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}]
            if read_only
            else []
        )
        assert engine.pool.checkedout() == 0  # type: ignore[attr-defined]
    finally:
        engine.dispose()
