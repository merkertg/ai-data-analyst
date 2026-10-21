"""Anomaly CLI validates early, preserves files, and emits exact safe JSON."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.analytics import anomalies as cli
from app.analytics.anomaly_models import Finding
from app.analytics.models import Period
from app.db.session import DatabaseNotConfigured

DATES = ["--start", "2026-01-01", "--end", "2026-10-01"]


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--start", "2026-01-01"],
        ["--start", "invalid", "--end", "2026-10-01"],
        ["--start", "2026-10-01", "--end", "2026-01-01"],
        ["--start", "2016-01-01", "--end", "2026-01-02"],
        DATES + ["--seed", "-1"],
        DATES + ["--seed", "4294967296"],
        DATES + ["--seed", "not-an-integer"],
    ],
)
def test_invalid_anomaly_arguments_fail_before_connecting(
    arguments: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed periods, incomplete arguments, and seeds cannot open a database."""
    engine_factory = MagicMock()
    monkeypatch.setattr(cli, "get_engine", engine_factory)

    with pytest.raises(SystemExit) as error:
        cli.main(arguments)

    assert error.value.code == 2
    engine_factory.assert_not_called()


def test_anomaly_json_keeps_exact_evidence_and_readonly_snapshot(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Decimals remain strings, dates stay ISO, and missing scores become null."""
    period = Period(date(2026, 1, 1), date(2026, 10, 1))
    finding = Finding(
        id="example",
        method="robust_zscore",
        kind="volume_shift",
        period=Period.month(2026, 9),
        entity={"category": "pumps"},
        metric="paid_quantity",
        observed=Decimal("999999999999999999999999.01"),
        baseline=Decimal("100.00"),
        score=None,
    )
    engine = MagicMock()
    session_factory = MagicMock()
    builder = MagicMock(return_value={"period": period, "findings": [finding]})
    monkeypatch.setattr(cli, "get_engine", lambda: engine)
    monkeypatch.setattr(cli, "Session", session_factory)
    monkeypatch.setattr(cli, "build_anomaly_report", builder)

    assert cli.main(DATES + ["--seed", "123"]) == 0

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["period"] == {"start": "2026-01-01", "end": "2026-10-01"}
    assert result["findings"][0]["period"] == {
        "start": "2026-09-01",
        "end": "2026-10-01",
    }
    assert result["findings"][0]["observed"] == "999999999999999999999999.01"
    assert result["findings"][0]["baseline"] == "100.00"
    assert result["findings"][0]["score"] is None
    assert not captured.err
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.assert_called_once_with(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    session_factory.assert_called_once_with(
        bind=connection.execution_options.return_value
    )
    builder.assert_called_once_with(
        session_factory.return_value.__enter__.return_value, period, 123
    )


def test_anomaly_output_creates_new_file_and_preserves_it_on_repeat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A saved report cannot be silently overwritten by a second invocation."""
    destination = tmp_path / "report.json"
    engine = MagicMock()
    monkeypatch.setattr(cli, "get_engine", MagicMock(return_value=engine))
    monkeypatch.setattr(cli, "Session", MagicMock())
    monkeypatch.setattr(
        cli, "build_anomaly_report", MagicMock(return_value={"findings": []})
    )
    arguments = DATES + ["--output", str(destination)]

    assert cli.main(arguments) == 0
    original = destination.read_bytes()
    assert json.loads(original) == {"findings": []}
    assert original.endswith(b"\n")
    assert not capsys.readouterr().out
    engine.connect.reset_mock()

    assert cli.main(arguments) == 1
    assert destination.read_bytes() == original
    engine.connect.assert_not_called()
    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err) == {
        "error": "Detection failed; check database, dates and output."
    }


@pytest.mark.parametrize(
    "error",
    [
        DatabaseNotConfigured("credential-do-not-print"),
        SQLAlchemyError("credential-do-not-print"),
        ValueError("credential-do-not-print"),
        OSError("credential-do-not-print"),
    ],
)
def test_anomaly_cli_sanitizes_failures_without_output(
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Driver, configuration, and filesystem details do not enter CLI errors."""
    monkeypatch.setattr(cli, "get_engine", MagicMock(side_effect=error))

    assert cli.main(DATES) == 1

    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err) == {
        "error": "Detection failed; check database, dates and output."
    }
    assert "credential-do-not-print" not in captured.err
