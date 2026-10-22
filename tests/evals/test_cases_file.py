"""The eval set itself: size, coverage and calls that the tools accept."""

import json

from app.agents.tools import TOOLS
from app.evals.cases import load_cases

CASES = load_cases()


def test_there_are_at_least_forty_questions() -> None:
    """The course asks for 30–50 questions with known answers."""
    assert 40 <= len(CASES) <= 50
    assert len({case.id for case in CASES}) == len(CASES)


def test_every_kind_and_both_languages_are_covered() -> None:
    """Metrics to refusals, in Russian and in English."""
    kinds = {case.kind for case in CASES}
    assert kinds == {
        "metric",
        "comparison",
        "contribution",
        "refunds",
        "products",
        "stock",
        "no_data",
        "refusal",
        "injection",
    }
    languages = [case.language for case in CASES]
    assert languages.count("en") >= 10 and languages.count("ru") >= 20


def test_reference_calls_are_valid_tool_calls() -> None:
    """Each reference call passes the same argument checks as a model's call."""
    for case in CASES:
        assert set(case.tools_any) <= set(TOOLS), case.id
        for call in case.reference:
            tool = TOOLS[call.tool]
            tool.arguments.model_validate_json(json.dumps(call.arguments))
            assert call.cite, case.id


def test_answerable_cases_have_expectations() -> None:
    """Every question except refusals names at least one value to cite."""
    for case in CASES:
        if case.no_facts:
            assert not case.expect and not case.reference, case.id
        else:
            assert case.expect and case.reference and case.tools_any, case.id


def test_refusals_require_an_answer_without_facts() -> None:
    """Writes, SQL and secrets: the right answer contains no facts."""
    refusals = [case for case in CASES if case.kind == "refusal"]
    assert len(refusals) >= 3
    assert all(case.no_facts for case in refusals)
    injection = [case for case in CASES if case.kind == "injection"]
    assert injection and all(case.forbidden_numbers for case in injection)
