"""The evidence check: a report may only state values that tools returned."""

import pytest

from app.agents.contracts import ToolTrace
from app.agents.evidence import MISSING, check_report, numbers_in, resolve
from app.agents.schemas import AnalysisReport, Evidence, Fact, Hypothesis

COMPARISON = ToolTrace(
    call_id="call_1",
    name="get_sales_by_category",
    arguments={},
    result={
        "ok": True,
        "data": {
            "net_revenue": {"absolute": "-291500.00", "percent": "-94.34"},
            "contributions": [
                {"name": "Насосы", "delta": "-300000.00"},
                {"name": "Датчики", "delta": "-9500.00"},
            ],
        },
    },
)
STOCK = ToolTrace(
    call_id="call_2",
    name="get_inventory_history",
    arguments={},
    result={
        "ok": True,
        "data": {"products": [{"name": "Demo pumps 01", "zero_stock_days": 10}]},
    },
)
FAILED = ToolTrace(
    call_id="call_3",
    name="get_revenue",
    arguments={},
    result={"ok": False, "error": {"code": "invalid_arguments", "message": "x"}},
)
TRACE = [COMPARISON, STOCK, FAILED]


def evidence(call_id: str, field: str, value: str) -> Evidence:
    """Shorthand for one evidence item."""
    return Evidence(call_id=call_id, field=field, value=value)


NET = evidence("call_1", "net_revenue.absolute", "-291500.00")
PERCENT = evidence("call_1", "net_revenue.percent", "-94.34")


def report(
    statement: str,
    items: list[Evidence],
    *,
    summary: str = "Выручка снизилась.",
    hypotheses: list[Hypothesis] | None = None,
    recommendations: list[str] | None = None,
    limitations: list[str] | None = None,
) -> AnalysisReport:
    """A report with one fact; the other parts can be overridden."""
    return AnalysisReport(
        language="ru",
        summary=summary,
        facts=[Fact(statement=statement, evidence=items)],
        hypotheses=hypotheses or [],
        recommendations=recommendations or [],
        limitations=limitations or [],
    )


def test_resolve_follows_keys_and_list_indexes() -> None:
    """Dotted paths reach nested values; a wrong path finds nothing."""
    data = COMPARISON.result["data"]

    assert resolve(data, "contributions.1.delta") == "-9500.00"
    assert resolve(data, "net_revenue") == data["net_revenue"]
    assert resolve(data, "contributions.9.delta") is MISSING
    assert resolve(data, "contributions.x") is MISSING


def test_a_verified_report_has_no_problems() -> None:
    """Exact values, a dropped sign and grouped digits are all accepted."""
    accepted = report(
        "Чистая выручка упала на 291 500.00 (−94.34%).",
        [NET, PERCENT],
        summary="Выручка снизилась на 291500.00.",
    )

    assert check_report(accepted, TRACE) == []


@pytest.mark.parametrize(
    ("item", "problem"),
    [
        (evidence("call_9", "net_revenue.absolute", "-291500.00"), "unknown call_id"),
        (evidence("call_3", "net_revenue.absolute", "-291500.00"), "returned an error"),
        (evidence("call_1", "net_revenue", "-291500.00"), "not a single value"),
        (evidence("call_1", "net_revenue.absolute", "-291000.00"), "not '-291000.00'"),
    ],
    ids=["unknown call", "failed call", "not a scalar", "wrong value"],
)
def test_bad_evidence_is_reported(item: Evidence, problem: str) -> None:
    """Evidence must point at one exact value of a successful call."""
    problems = check_report(report("Выручка снизилась.", [item]), TRACE)

    assert any(problem in text for text in problems), problems


def test_a_number_without_evidence_is_rejected() -> None:
    """The model cannot add a figure that no tool returned."""
    problems = check_report(report("Выручка упала на 300000.00.", [NET]), TRACE)

    assert problems == ["facts[0]: number '300000.00' is not in its evidence"]


def test_a_fact_needs_evidence() -> None:
    """A statement without evidence is not a fact."""
    problems = check_report(report("Выручка снизилась.", []), TRACE)

    assert problems == ["facts[0]: a fact needs at least one evidence item"]


def test_summary_and_recommendations_reuse_fact_values_only() -> None:
    """Numbers outside facts must match some verified evidence value."""
    checked = report(
        "Выручка упала на 291500.00.",
        [NET],
        summary="Падение 291500.00, то есть 95%.",
        recommendations=["Вернуть 300000.00 продаж."],
    )

    assert check_report(checked, TRACE) == [
        "summary: number '95' is not in any evidence",
        "recommendations[0]: number '300000.00' is not in any evidence",
    ]


def test_cited_names_with_digits_are_not_figures() -> None:
    """Digits inside a quoted product name are part of the name."""
    hypothesis = Hypothesis(
        statement="Demo pumps 01 был без остатка 10 дн.",
        evidence=[
            evidence("call_2", "products.0.name", "Demo pumps 01"),
            evidence("call_2", "products.0.zero_stock_days", "10"),
        ],
    )

    assert (
        check_report(
            report("Выручка упала на 291500.00.", [NET], hypotheses=[hypothesis]), TRACE
        )
        == []
    )


def test_numbers_in_skips_dates_contextual_years_and_codes() -> None:
    """ISO dates, contextual years and codes such as A01 need no evidence."""
    text = "С 2026-09-01 по сентябрь 2026: A01, ЦН-100 и DN50 дали -1 000,50 и 1,931."

    assert numbers_in(text) == ["-1 000,50", "1,931"]


@pytest.mark.parametrize(
    "statement",
    [
        "Чистая выручка составила 2000 рублей.",
        "Невыполненных заказов 2026.",
        "Выручка выросла на 999999руб.",
        "Revenue grew by 999999RUB.",
        "Refunds grew by 999999%.",
    ],
)
def test_amounts_counts_and_adjacent_units_need_evidence(statement: str) -> None:
    """Year-like values and units without spaces cannot hide invented figures."""
    problems = check_report(report(statement, [NET]), TRACE)

    assert len(problems) == 1
    assert "is not in its evidence" in problems[0]


@pytest.mark.parametrize(
    "calendar",
    [
        "За сентябрь 2026 выручка упала.",
        "В сентябре 2026 года выручка упала.",
        "В 2026 году выручка упала.",
        "В 2026 г. выручка упала.",
        "Revenue fell in September 2026.",
        "Revenue fell in Sep. 2026.",
        "Revenue fell in the year 2026.",
        "2026 September revenue fell.",
    ],
)
def test_explicit_calendar_years_need_no_numeric_evidence(calendar: str) -> None:
    """Calendar labels remain usable without treating any four digits as a year."""
    assert check_report(report(calendar, [NET]), TRACE) == []


def test_numbers_in_limitations_need_global_evidence() -> None:
    """Limitations share the same numeric guard as summary and recommendations."""
    checked = report(
        "Выручка упала на 291500.00.",
        [NET],
        limitations=["Данных о 999999999 заказах нет."],
    )

    assert check_report(checked, TRACE) == [
        "limitations[0]: number '999999999' is not in any evidence"
    ]


def test_limitations_may_reuse_verified_values_and_names() -> None:
    """A limitation can quote supported figures and cited product names."""
    checked = report(
        "Товар Demo pumps 01 был без остатка 10 дн.",
        [
            evidence("call_2", "products.0.name", "Demo pumps 01"),
            evidence("call_2", "products.0.zero_stock_days", "10"),
        ],
        limitations=["Для Demo pumps 01 подтверждены только 10 дней без остатка."],
    )

    assert check_report(checked, TRACE) == []


@pytest.mark.parametrize(
    ("written", "value"),
    [
        ("1,931", "1931"),
        ("242 542,35", "242542.35"),
        ("165,497,371.86", "-165497371.86"),
        ("−26.18", "-26.18"),
    ],
)
def test_number_formats_match_exact_values(written: str, value: str) -> None:
    """Thousands separators, decimal commas and minus signs are understood."""
    trace = [ToolTrace("call_1", "x", {}, {"ok": True, "data": {"value": value}})]
    checked = report(f"Значение {written}.", [evidence("call_1", "value", value)])

    assert check_report(checked, trace) == []
