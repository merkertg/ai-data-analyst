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


def findings(report: dict[str, object]) -> set[tuple[str, str]]:
    """(package, vulnerability id) pairs from a pip-audit JSON report."""
    found = set()
    for dependency in report["dependencies"]:  # type: ignore[attr-defined]
        for vulnerability in dependency.get("vulns", []):
            found.add((dependency["name"].lower(), vulnerability["id"]))
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
    # Exit code 1 only means "vulnerabilities found"; they are judged below.
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
    today = date.today()
    accepted = load_exceptions(today)
    found = findings(json.loads(output.read_text(encoding="utf-8")))
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
