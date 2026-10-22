"""Audit the locked runtime dependencies for known vulnerabilities.

    uv run python scripts/audit_dependencies.py

1. `uv export` writes the exact runtime versions with hashes (no dev tools).
2. pip-audit checks them against the PyPI advisory database.
3. Every finding must be listed in scripts/audit-exceptions.json with a reason
   and an expiry date not later than 30 days ahead. An unlisted finding, an
   expired exception or an exception for a finding that no longer exists
   fails the audit: accepted risk stays visible and temporary.

The JSON report is written to reports/pip-audit.json for CI artifacts.
"""

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = ROOT / "scripts" / "audit-exceptions.json"
REPORTS = ROOT / "reports"
PIP_AUDIT = "pip-audit==2.10.1"
MAX_EXCEPTION_DAYS = 30


def load_exceptions(today: date) -> dict[tuple[str, str], dict[str, str]]:
    """Accepted findings by (package, id); invalid entries stop the audit."""
    entries = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["exceptions"]
    accepted = {}
    for entry in entries:
        expires = date.fromisoformat(entry["expires"])
        if not entry.get("reason", "").strip():
            raise ValueError(f"{entry['id']}: an exception needs a reason")
        if expires > today + timedelta(days=MAX_EXCEPTION_DAYS):
            raise ValueError(f"{entry['id']}: expiry more than 30 days ahead")
        accepted[(entry["package"].lower(), entry["id"])] = entry
    return accepted


def findings(report: object) -> set[tuple[str, str]]:
    """Validate report fields before extracting package and vulnerability pairs."""
    if not isinstance(report, dict) or not isinstance(report.get("dependencies"), list):
        raise ValueError("expected a dependencies list")
    found: set[tuple[str, str]] = set()
    for dependency in report["dependencies"]:
        if not isinstance(dependency, dict):
            raise ValueError("expected a dependency object")
        name = dependency.get("name")
        vulnerabilities = dependency.get("vulns")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("expected a non-empty dependency name")
        if not isinstance(vulnerabilities, list):
            raise ValueError(f"{name}: expected a vulnerabilities list")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise ValueError(f"{name}: expected a vulnerability object")
            identifier = vulnerability.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError(f"{name}: expected a non-empty vulnerability id")
            found.add((name.lower(), identifier))
    return found


def main() -> int:
    """Export, audit, compare with the accepted list; non-zero on any problem."""
    REPORTS.mkdir(exist_ok=True)
    requirements = REPORTS / "runtime-requirements.txt"
    subprocess.run(
        [
            "uv", "export", "--locked", "--no-dev", "--no-emit-project",
            "--format", "requirements.txt", "--output-file", str(requirements),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )  # fmt: skip
    output = REPORTS / "pip-audit.json"
    # A failed invocation must never reuse an earlier successful report.
    output.unlink(missing_ok=True)
    # Exit code 1 may also mean an operational failure, so require fresh findings.
    audit = subprocess.run(
        [
            "uv", "tool", "run", "--python", "3.12", "--from", PIP_AUDIT,
            "pip-audit", "--strict", "--require-hashes", "--disable-pip",
            "--progress-spinner", "off", "-r", str(requirements),
            "--format", "json", "--output", str(output),
        ],
        check=False,
    )  # fmt: skip
    if audit.returncode not in {0, 1} or not output.exists():
        print("pip-audit did not produce a report", file=sys.stderr)
        return 2
    try:
        found = findings(json.loads(output.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, ValueError) as error:
        print(f"pip-audit produced an invalid report: {error}", file=sys.stderr)
        return 2
    if bool(found) != (audit.returncode == 1):
        print("pip-audit exit status does not match its findings", file=sys.stderr)
        return 2
    today = date.today()
    accepted = load_exceptions(today)
    problems = [
        f"not accepted: {package} {vid}"
        for package, vid in sorted(found - set(accepted))
    ]
    for key, entry in sorted(accepted.items()):
        if key not in found:
            problems.append(f"stale exception, remove it: {key[0]} {key[1]}")
        elif date.fromisoformat(entry["expires"]) < today:
            problems.append(
                f"expired exception: {key[0]} {key[1]} ({entry['expires']})"
            )
    print(f"{len(found)} known vulnerabilities, {len(found & set(accepted))} accepted")
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
