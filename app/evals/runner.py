"""Run eval cases through the real agent runtime and score every answer.

The runtime, tools and evidence check are the production ones; only the
provider changes (reference, mock or OpenAI). Nothing is written to the
database: runs are scored in memory and returned as a JSON-ready report.
"""

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.agents.contracts import AgentProgress, AgentProvider
from app.agents.evidence import written_numbers
from app.agents.runtime import AgentRuntime, ToolRunner
from app.agents.schemas import AnalysisReport
from app.evals.cases import EvalCase, expected_values, same_value
from app.evals.oracle import Oracle
from app.llm.config import LLMSettings
from app.llm.errors import LLMError

# Fixed "today" for reproducible runs: the demo data ends on 2026-09-30.
EVAL_TODAY = date(2026, 10, 1)
ProviderForCase = Callable[[EvalCase], AgentProvider]


@dataclass
class CaseResult:
    """How one question was answered and which checks passed."""

    id: str
    kind: str
    language: str
    question: str
    passed: bool
    checks: dict[str, bool]
    expected: list[dict[str, Any]]
    tools_required: bool
    tools_called: list[str]
    facts: int
    error: str | None
    latency_ms: int
    total_tokens: int | None
    summary: str | None = None
    notes: list[str] = field(default_factory=list)


def _cited(report: AnalysisReport) -> list[str]:
    """Evidence values of facts and hypotheses (both are verified)."""
    parts = [*(fact.evidence for fact in report.facts)]
    parts += [hypothesis.evidence for hypothesis in report.hypotheses]
    return [item.value for evidence in parts for item in evidence]


def _texts(report: AnalysisReport) -> list[str]:
    """Every sentence the user reads."""
    return [
        report.summary,
        *(fact.statement for fact in report.facts),
        *(hypothesis.statement for hypothesis in report.hypotheses),
        *report.recommendations,
        *report.limitations,
    ]


def score(
    case: EvalCase,
    report: AnalysisReport | None,
    progress: AgentProgress,
    error: str | None,
    oracle: Oracle,
) -> tuple[dict[str, bool], list[dict[str, Any]], list[str]]:
    """Checks for one answer; a failed run passes none of them."""
    succeeded = [
        item.name for item in progress.tool_trace if item.result.get("ok") is True
    ]
    expected = [
        {
            **expectation.model_dump(mode="json", exclude_none=True),
            "values": sorted(expected_values(expectation, oracle)),
        }
        for expectation in case.expect
    ]
    if report is None:
        checks = {"completed": False}
        return checks, expected, [f"run failed: {error}"]
    cited = _cited(report)
    notes = []
    for item in expected:
        item["found"] = any(
            same_value(value, wanted) for value in cited for wanted in item["values"]
        )
        if not item["found"]:
            notes.append(f"{item['metric']}: expected one of {item['values']}")
    written = set().union(*(written_numbers(text) for text in _texts(report)))
    forbidden = {abs(Decimal(number)) for number in case.forbidden_numbers}
    checks = {
        "completed": True,
        "language": report.language == case.language,
        "tools": not case.tools_any
        or any(name in case.tools_any for name in succeeded),
        "values": all(item["found"] for item in expected),
        "no_facts": not case.no_facts or not report.facts,
        "forbidden": not written & forbidden,
    }
    if not checks["language"]:
        notes.append(f"answered in {report.language}, asked in {case.language}")
    if not checks["tools"]:
        notes.append(f"none of {case.tools_any} succeeded")
    if not checks["no_facts"]:
        notes.append("facts were reported for an out-of-scope question")
    if not checks["forbidden"]:
        notes.append("a planted number appears in the answer")
    return checks, expected, notes


def run_case(
    case: EvalCase,
    provider: AgentProvider,
    run_tool: ToolRunner,
    settings: LLMSettings,
    oracle: Oracle,
) -> CaseResult:
    """Ask one question with the production runtime and score the answer."""
    runtime = AgentRuntime(provider, run_tool, settings, today=lambda: EVAL_TODAY)
    started = time.perf_counter()
    report, error = None, None
    try:
        report = runtime.run(case.question).report
    except LLMError as failure:
        error = failure.code
    latency_ms = round((time.perf_counter() - started) * 1000)
    progress = runtime.progress
    checks, expected, notes = score(case, report, progress, error, oracle)
    return CaseResult(
        id=case.id,
        kind=case.kind,
        language=case.language,
        question=case.question,
        passed=all(checks.values()),
        checks=checks,
        expected=expected,
        tools_required=bool(case.tools_any),
        tools_called=[item.name for item in progress.tool_trace],
        facts=0 if report is None else len(report.facts),
        error=error,
        latency_ms=latency_ms,
        total_tokens=None if progress.usage is None else progress.usage.total_tokens,
        summary=None if report is None else report.summary,
        notes=notes,
    )


def _rate(hits: int, total: int) -> float | None:
    """A share rounded for reading; None when nothing was measured."""
    return None if total == 0 else round(hits / total, 4)


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    """Pass rates overall, per kind and per check."""
    by_kind: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_kind.setdefault(result.kind, {"passed": 0, "total": 0})
        bucket["total"] += 1
        bucket["passed"] += result.passed
    expectations = [item for result in results for item in result.expected]
    # Questions without a required tool cannot earn free hits, and a failed
    # run remains a miss instead of disappearing from the denominator.
    tool_cases = [r for r in results if r.tools_required]
    refusal = [r for r in results if r.kind == "refusal"]
    latencies = sorted(result.latency_ms for result in results)
    tokens = [r.total_tokens for r in results if r.total_tokens is not None]
    return {
        "cases": len(results),
        "passed": sum(result.passed for result in results),
        "pass_rate": _rate(sum(result.passed for result in results), len(results)),
        "completed_rate": _rate(
            sum(result.checks["completed"] for result in results), len(results)
        ),
        "tool_selection_rate": _rate(
            sum(r.checks.get("tools", False) for r in tool_cases), len(tool_cases)
        ),
        "value_accuracy": _rate(
            sum(bool(item.get("found")) for item in expectations), len(expectations)
        ),
        "refusal_rate": _rate(sum(r.passed for r in refusal), len(refusal)),
        "by_kind": dict(sorted(by_kind.items())),
        "latency_ms": {
            "median": latencies[len(latencies) // 2] if latencies else None,
            "max": latencies[-1] if latencies else None,
        },
        "total_tokens": sum(tokens) if tokens else None,
    }


def run_all(
    cases: list[EvalCase],
    provider_for: ProviderForCase,
    run_tool: ToolRunner,
    settings: LLMSettings,
    oracle: Oracle,
) -> dict[str, Any]:
    """Run every case and return the summary with per-case results."""
    results = [
        run_case(case, provider_for(case), run_tool, settings, oracle) for case in cases
    ]
    return {
        "today": EVAL_TODAY.isoformat(),
        "summary": summarize(results),
        "cases": [asdict(result) for result in results],
    }
