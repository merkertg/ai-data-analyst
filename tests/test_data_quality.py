"""Quality report and CLI behaviour without a database or configuration files."""

import json
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.data import quality
from app.data.quality import QualityCheck, QualityReport
from app.db.session import DatabaseNotConfigured


def test_report_is_json_serializable_and_preserves_check_order() -> None:
    """Consumers receive plain ordered data and a failed result for any violation."""
    report = QualityReport((QualityCheck("first", 0), QualityCheck("second", 2)))

    assert not report.passed
    assert json.loads(json.dumps(report.as_dict())) == {
        "passed": False,
        "checks": [
            {"name": "first", "violations": 0},
            {"name": "second", "violations": 2},
        ],
    }


def test_zero_violations_pass() -> None:
    """All-zero results pass, including an empty tuple of checks."""
    assert QualityReport((QualityCheck("rule", 0),)).passed
    assert QualityReport(()).passed


def test_check_and_report_are_frozen() -> None:
    """A caller cannot accidentally change a published quality result."""
    check = QualityCheck("rule", 0)
    report = QualityReport((check,))

    with pytest.raises(FrozenInstanceError):
        check.violations = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        report.checks = ()  # type: ignore[misc]


@pytest.mark.parametrize("violations, expected_exit", [(0, 0), (1, 1)])
def test_cli_prints_report_and_returns_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    violations: int,
    expected_exit: int,
) -> None:
    """CLI exit codes let a shell stop when database business rules fail."""
    report = QualityReport((QualityCheck("empty_orders", violations),))
    session_factory = MagicMock()
    monkeypatch.setattr(quality, "get_engine", MagicMock())
    monkeypatch.setattr(quality, "Session", session_factory)
    monkeypatch.setattr(quality, "check_quality", lambda session: report)

    assert quality.main() == expected_exit

    output = capsys.readouterr()
    assert json.loads(output.out) == report.as_dict()
    assert not output.err
    session_factory.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        DatabaseNotConfigured("password=secret"),
        SQLAlchemyError("postgresql://analyst:secret@host/database"),
        ValueError("invalid configuration with password=secret"),
    ],
)
def test_cli_database_errors_do_not_expose_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    """Unavailable or invalid configuration returns one sanitized JSON error."""
    monkeypatch.setattr(quality, "get_engine", MagicMock(side_effect=error))

    assert quality.main() == 1

    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err) == {
        "error": "Data quality check could not access the database."
    }
    assert "secret" not in output.err
