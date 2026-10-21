"""CLI validation, exact JSON values and sanitized errors without a database."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.analytics import __main__ as cli
from app.analytics.models import Period, PeriodMetrics
from app.db.session import DatabaseNotConfigured

DATES = ["--start", "2026-09-01", "--end", "2026-10-01"]


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--start", "invalid", "--end", "2026-10-01"],
        ["--start", "2026-10-01", "--end", "2026-09-01"],
        DATES + ["--compare-start", "2026-08-01"],
        DATES + ["--compare-end", "2026-09-01"],
        DATES + ["--dimension", "category; DROP TABLE orders"],
    ],
)
def test_invalid_arguments_do_not_connect(
    arguments: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid periods, incomplete comparisons and unknown dimensions fail early."""
    engine_factory = MagicMock()
    monkeypatch.setattr(cli, "get_engine", engine_factory)

    with pytest.raises(SystemExit) as error:
        cli.main(arguments)

    assert error.value.code == 2
    engine_factory.assert_not_called()


def test_cli_preserves_decimal_values_and_uses_consistent_read_transaction(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Large exact amounts, nullable AOV and dates survive JSON without floats."""
    period = Period(date(2026, 9, 1), date(2026, 10, 1))
    metrics = PeriodMetrics(
        period=period,
        paid_sales=Decimal("999999999999.99"),
        refunds=Decimal("0.00"),
        net_revenue=Decimal("999999999999.99"),
        paid_orders=0,
        average_order_value=None,
    )
    engine = MagicMock()
    report_builder = MagicMock(return_value={"summary": metrics, "comparison": None})
    monkeypatch.setattr(cli, "get_engine", lambda: engine)
    monkeypatch.setattr(cli, "Session", MagicMock())
    monkeypatch.setattr(cli, "build_report", report_builder)

    assert cli.main(DATES) == 0

    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["summary"]["paid_sales"] == "999999999999.99"
    assert result["summary"]["average_order_value"] is None
    assert result["summary"]["period"] == {
        "start": "2026-09-01",
        "end": "2026-10-01",
    }
    assert result["comparison"] is None
    assert not output.err
    engine.connect.return_value.__enter__.return_value.execution_options.assert_called_once_with(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )


@pytest.mark.parametrize(
    "error",
    [
        DatabaseNotConfigured("credential-do-not-print"),
        SQLAlchemyError("credential-do-not-print"),
        ValueError("credential-do-not-print"),
    ],
)
def test_database_errors_are_sanitized(
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Configuration and driver details never enter a failed report or stderr."""
    monkeypatch.setattr(cli, "get_engine", MagicMock(side_effect=error))

    assert cli.main(DATES) == 1

    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err) == {
        "error": "Analytics report failed; check database settings and periods."
    }
    assert "credential-do-not-print" not in output.err
