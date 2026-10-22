"""The Pandas oracle on the hand-made CSV bundle (tests/evals/conftest.py)."""

from datetime import date

import pytest

from app.evals.cases import Expectation, expected_values
from app.evals.oracle import Oracle, money

SEP = (date(2026, 9, 1), date(2026, 10, 1))
OCT = (date(2026, 10, 1), date(2026, 11, 1))
EMPTY = (date(2026, 12, 1), date(2027, 1, 1))
REFUND_ONLY = (date(2026, 10, 2), date(2026, 10, 3))


def test_period_totals_match_the_hand_calculation(oracle: Oracle) -> None:
    """September: 310 000.00 + 899.99 + 0.03; refunds only of paid orders.

    Net change October vs September: 17 500.00 − 309 900.02 = −292 400.02;
    sensor refund rate: 1 000.00 / 10 899.99 = 9.17 %.
    """
    september = oracle.totals(SEP)
    october = oracle.totals(OCT)

    assert money(september.sales) == money(31090002)
    assert (money(september.refunds), september.orders) == (money(100000), 3)
    assert (money(october.sales), money(october.refunds), october.orders) == (
        money(1800000),
        money(50000),
        1,
    )


def test_line_amounts_round_half_up_to_kopecks(oracle: Oracle) -> None:
    """899.991 → 899.99 and 0.025 → 0.03, like PostgreSQL ROUND(…, 2)."""
    amounts = sorted(oracle.lines["amount"].tolist())

    assert amounts[:2] == [3, 89999]


@pytest.mark.parametrize(
    ("expectation", "values"),
    [
        (Expectation(metric="net_revenue", period=OCT), {"17500.00"}),
        (
            Expectation(
                metric="change_absolute", of="net_revenue", period=OCT, previous=SEP
            ),
            {"-292400.02"},
        ),
        (
            Expectation(
                metric="group_delta",
                dimension="category",
                name="Насосы",
                period=OCT,
                previous=SEP,
            ),
            {"-300000.00"},
        ),
        (
            Expectation(
                metric="largest_decline", dimension="region", period=OCT, previous=SEP
            ),
            {"Северо-Запад"},
        ),
        (Expectation(metric="refund_rate", name="Датчики", period=SEP), {"9.17"}),
        (Expectation(metric="top_product", period=SEP), {"PMP-100", "Pump"}),
        (Expectation(metric="zero_stock_days", name="PMP-100", period=SEP), {"1"}),
        (Expectation(metric="last_stock_quantity", name="PMP-100", period=SEP), {"4"}),
        (Expectation(metric="max_line_quantity", name="Датчики", period=SEP), {"5"}),
        (Expectation(metric="first_paid_on"), {"2026-09-05"}),
    ],
)
def test_expected_values(
    oracle: Oracle, expectation: Expectation, values: set[str]
) -> None:
    """Each metric kind gives the value computed by hand from the rows above."""
    assert expected_values(expectation, oracle) == values


@pytest.mark.parametrize("period", [EMPTY, REFUND_ONLY], ids=["empty", "refund-only"])
def test_average_order_value_without_paid_orders_is_null(
    oracle: Oracle, period: tuple[date, date]
) -> None:
    """Refund activity cannot define an average when there are no paid orders."""
    assert expected_values(
        Expectation(metric="average_order_value", period=period), oracle
    ) == {"null"}


@pytest.mark.parametrize("metric", ["change_absolute", "change_percent"])
@pytest.mark.parametrize(
    ("period", "previous"),
    [
        (EMPTY, SEP),
        (SEP, EMPTY),
        (REFUND_ONLY, SEP),
        (SEP, REFUND_ONLY),
        (EMPTY, EMPTY),
    ],
    ids=[
        "empty-current",
        "empty-previous",
        "refund-current",
        "refund-previous",
        "both-empty",
    ],
)
def test_aov_change_propagates_missing_operands(
    oracle: Oracle,
    metric: str,
    period: tuple[date, date],
    previous: tuple[date, date],
) -> None:
    """Neither absolute nor percent changes may replace an undefined AOV with zero."""
    expectation = Expectation.model_validate(
        {
            "metric": metric,
            "of": "average_order_value",
            "period": period,
            "previous": previous,
        }
    )
    assert expected_values(expectation, oracle) == {"null"}


@pytest.mark.parametrize(
    "expectation",
    [
        Expectation(
            metric="change_percent", of="net_revenue", period=SEP, previous=EMPTY
        ),
        Expectation(
            metric="change_percent", of="paid_orders", period=SEP, previous=EMPTY
        ),
        Expectation(metric="refund_rate", name="Датчики", period=EMPTY),
        Expectation(metric="refund_rate", name="Датчики", period=REFUND_ONLY),
        Expectation(
            metric="group_share",
            dimension="category",
            name="Насосы",
            period=EMPTY,
            previous=EMPTY,
        ),
    ],
    ids=[
        "zero-revenue-base",
        "zero-order-base",
        "empty-refund-rate",
        "refunds-without-sales",
        "zero-total-contribution",
    ],
)
def test_undefined_rates_use_json_null(
    oracle: Oracle, expectation: Expectation
) -> None:
    """The oracle quotes the same null token as the SQL tool's JSON evidence."""
    assert expected_values(expectation, oracle) == {"null"}


@pytest.mark.parametrize(
    ("expectation", "values"),
    [
        (Expectation(metric="net_revenue", period=REFUND_ONLY), {"-500.00"}),
        (Expectation(metric="paid_orders", period=REFUND_ONLY), {"0"}),
        (
            Expectation(
                metric="change_absolute", of="net_revenue", period=EMPTY, previous=SEP
            ),
            {"-309900.02"},
        ),
        (
            Expectation(
                metric="change_percent", of="net_revenue", period=EMPTY, previous=SEP
            ),
            {"-100.00"},
        ),
        (
            Expectation(
                metric="change_absolute", of="paid_orders", period=EMPTY, previous=EMPTY
            ),
            {"0"},
        ),
    ],
)
def test_defined_zero_and_refund_only_values_stay_numeric(
    oracle: Oracle, expectation: Expectation, values: set[str]
) -> None:
    """Missing AOV must not turn valid zero counts or negative net revenue into null."""
    assert expected_values(expectation, oracle) == values
