"""The Pandas oracle on the hand-made CSV bundle (tests/evals/conftest.py)."""

from datetime import date

import pytest

from app.evals.cases import Expectation, expected_values
from app.evals.oracle import Oracle, money

SEP = (date(2026, 9, 1), date(2026, 10, 1))
OCT = (date(2026, 10, 1), date(2026, 11, 1))


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
