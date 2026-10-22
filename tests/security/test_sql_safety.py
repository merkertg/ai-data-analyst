"""SQL limits: bound parameters, read-only tool sessions and a statement timeout."""

import json
from contextlib import AbstractContextManager, nullcontext

import pytest
from psycopg import errors
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.agents.tools import TOOLS, ToolExecutor
from app.api import dependencies
from app.api.agents import get_tool_sessions
from app.db.sample import add_sample_data
from app.db.session import create_database_engine

TABLES = [
    "customers",
    "products",
    "orders",
    "order_items",
    "refunds",
    "inventory_snapshots",
    "reports",
    "agent_runs",
    "api_tokens",
]
PAYLOADS = [
    "Насосы' OR '1'='1",
    "x'; DROP TABLE orders; --",
    'Насосы" ; DELETE FROM refunds; --',
    "../../.env",
    "$(cat /etc/passwd)",
    "%' UNION SELECT token_hash FROM api_tokens --",
]


def counts(session: Session) -> dict[str, int]:
    """Row counts of every table, to prove nothing was changed."""
    return {
        table: int(session.scalar(text(f"SELECT COUNT(*) FROM {table}")) or 0)
        for table in TABLES
    }


@pytest.fixture
def sample(db_session: Session) -> Session:
    """The documented sample in the rolled-back test transaction."""
    add_sample_data(db_session)
    return db_session


def executor(session: Session) -> ToolExecutor:
    """Tools reading the test transaction."""

    def sessions() -> AbstractContextManager[Session]:
        return nullcontext(session)

    return ToolExecutor(sessions)


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize(
    "tool", ["get_top_products", "detect_anomalies", "get_inventory_history"]
)
def test_injection_in_tool_arguments_is_only_data(
    sample: Session, tool: str, payload: str
) -> None:
    """A hostile category is a bound value: no rows match, nothing changes."""
    before = counts(sample)
    arguments = {
        "start": "2026-01-01",
        "end": "2026-11-01",
        "category": payload,
        "limit": 5,
    }

    _, result = executor(sample)(tool, json.dumps(arguments))

    assert result["ok"] is True
    rows = result["data"].get("products", result["data"].get("findings"))
    assert rows == []
    assert counts(sample) == before


def test_tool_sessions_are_read_only(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every tool runs in a session that PostgreSQL itself keeps read-only."""
    monkeypatch.setattr(dependencies, "get_engine", lambda: migrated_engine)
    sessions = get_tool_sessions()
    run = ToolExecutor(sessions)
    period: dict[str, object] = {"start": "2026-09-01", "end": "2026-10-01"}
    comparison: dict[str, object] = {
        **period,
        "compare_start": "2026-08-01",
        "compare_end": "2026-09-01",
    }
    listing: dict[str, object] = {**period, "category": None, "limit": 3}
    arguments_by_tool: dict[str, dict[str, object]] = {
        "get_data_coverage": {},
        "get_revenue": period,
        "get_refund_statistics": period,
        "get_top_products": listing,
        "detect_anomalies": listing,
        "get_inventory_history": listing,
    }
    for name in TOOLS:
        arguments = arguments_by_tool.get(name, comparison)
        _, result = run(name, json.dumps(arguments))
        assert result["ok"] is True, name

    with sessions() as session:
        isolation = session.scalar(text("SHOW transaction_isolation"))
        with pytest.raises(DBAPIError) as error:
            session.execute(text("DELETE FROM api_tokens"))
    assert isolation == "repeatable read"
    assert isinstance(error.value.orig, errors.ReadOnlySqlTransaction)


def test_statement_timeout_stops_long_queries(test_database_url: str) -> None:
    """PostgreSQL cancels a statement that runs longer than the limit."""
    engine = create_database_engine(test_database_url, statement_timeout_ms=200)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SHOW statement_timeout")) == "200ms"
            with pytest.raises(OperationalError) as error:
                connection.execute(text("SELECT pg_sleep(2)"))
        assert isinstance(error.value.orig, errors.QueryCanceled)
    finally:
        engine.dispose()


def test_default_statement_timeout_is_set(test_database_url: str) -> None:
    """Without an explicit value the application uses 15 seconds."""
    engine = create_database_engine(test_database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SHOW statement_timeout")) == "15s"
    finally:
        engine.dispose()
