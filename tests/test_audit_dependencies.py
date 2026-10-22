"""Audit subprocess failures cannot reuse stale or malformed JSON artifacts."""

import json
import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts import audit_dependencies as audit

CLEAN_REPORT = json.dumps({"dependencies": [{"name": "example", "vulns": []}]})
FINDING_REPORT = json.dumps(
    {"dependencies": [{"name": "Example", "vulns": [{"id": "TEST-2026-1"}]}]}
)


@dataclass
class AuditProcess:
    """Replace both external commands and optionally write the audit artifact."""

    reports: Path
    returncode: int = 0
    report: str | None = CLEAN_REPORT
    calls: list[list[str]] = field(default_factory=list)

    def run(
        self, command: list[str], *, check: bool, stdout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Emulate export followed by a fresh audit without launching subprocesses."""
        self.calls.append(command)
        if command[1] == "export":
            assert check
            assert stdout == subprocess.DEVNULL
            return subprocess.CompletedProcess(command, 0)
        assert not check
        output = self.reports / "pip-audit.json"
        assert not output.exists(), "the prior audit report must be removed first"
        assert command[-1] == str(output)
        if self.report is not None:
            output.write_text(self.report, encoding="utf-8")
        return subprocess.CompletedProcess(command, self.returncode)


@pytest.fixture
def process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuditProcess:
    """Keep reports and exception policy temporary and stub every external call."""
    reports = tmp_path / "reports"
    exceptions = tmp_path / "exceptions.json"
    exceptions.write_text('{"exceptions": []}', encoding="utf-8")
    stub = AuditProcess(reports)
    monkeypatch.setattr(audit, "REPORTS", reports)
    monkeypatch.setattr(audit, "EXCEPTIONS", exceptions)
    monkeypatch.setattr(subprocess, "run", stub.run)
    return stub


def accept_finding() -> None:
    """Accept the synthetic advisory temporarily using the existing policy format."""
    audit.EXCEPTIONS.write_text(
        json.dumps(
            {
                "exceptions": [
                    {
                        "package": "example",
                        "id": "TEST-2026-1",
                        "reason": "Synthetic test fixture",
                        "expires": (date.today() + timedelta(days=7)).isoformat(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize("old_report", [CLEAN_REPORT, FINDING_REPORT])
def test_failed_audit_cannot_reuse_existing_report(
    process: AuditProcess, old_report: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A valid old report is removed even when its findings were all accepted."""
    process.reports.mkdir()
    output = process.reports / "pip-audit.json"
    output.write_text(old_report, encoding="utf-8")
    if old_report == FINDING_REPORT:
        accept_finding()
    process.returncode = 1
    process.report = None

    assert audit.main() == 2
    assert not output.exists()
    assert len(process.calls) == 2
    assert "did not produce a report" in capsys.readouterr().err


def test_clean_audit_passes(process: AuditProcess) -> None:
    """A fresh clean report with successful exit status passes the audit."""
    assert audit.main() == 0
    assert len(process.calls) == 2


def test_unaccepted_finding_fails(
    process: AuditProcess, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fresh findings still fail unless the existing exception policy accepts them."""
    process.returncode = 1
    process.report = FINDING_REPORT
    assert audit.main() == 1
    assert "not accepted: example TEST-2026-1" in capsys.readouterr().err


def test_accepted_finding_passes(process: AuditProcess) -> None:
    """A fresh finding with an unexpired matching exception remains accepted."""
    process.returncode = 1
    process.report = FINDING_REPORT
    accept_finding()
    assert audit.main() == 0


@pytest.mark.parametrize("returncode", [2, 3, -15])
def test_operational_exit_codes_fail(process: AuditProcess, returncode: int) -> None:
    """An operational exit status fails even if the command writes valid JSON."""
    process.returncode = returncode
    assert audit.main() == 2


@pytest.mark.parametrize("returncode", [0, 1])
def test_missing_report_fails(process: AuditProcess, returncode: int) -> None:
    """Neither a successful status nor the findings status substitutes for a report."""
    process.returncode = returncode
    process.report = None
    assert audit.main() == 2


@pytest.mark.parametrize(
    "report",
    [
        "{unfinished",
        "[]",
        "{}",
        '{"dependencies": {}}',
        '{"dependencies": [null]}',
        '{"dependencies": [{"name": 5, "vulns": []}]}',
        '{"dependencies": [{"name": "example", "vulns": {}}]}',
        '{"dependencies": [{"name": "example", "vulns": [null]}]}',
        '{"dependencies": [{"name": "example", "vulns": [{"id": ""}]}]}',
    ],
)
def test_invalid_report_fails(
    process: AuditProcess, report: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Malformed and structurally incomplete reports fail with a clear diagnostic."""
    process.returncode = 1
    process.report = report
    assert audit.main() == 2
    assert "invalid report" in capsys.readouterr().err


@pytest.mark.parametrize("returncode,report", [(1, CLEAN_REPORT), (0, FINDING_REPORT)])
def test_inconsistent_report_and_exit_status_fail(
    process: AuditProcess,
    returncode: int,
    report: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean JSON result cannot turn an operational exit code of one into success."""
    process.returncode = returncode
    process.report = report
    assert audit.main() == 2
    assert "exit status does not match" in capsys.readouterr().err
