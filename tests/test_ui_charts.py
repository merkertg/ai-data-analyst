"""Chart coordinates are approximate; labels and downloads retain exact money."""

from decimal import Decimal

import pytest

from app.schemas.analytics import (
    ContributionsResponse,
    OrdersResponse,
    RevenueResponse,
)
from ui.charts import (
    contribution_chart,
    money,
    orders_chart,
    percentage,
    revenue_chart,
)

PERIOD = {"start": "2026-09-01", "end": "2026-10-01"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "—"),
        (Decimal("0"), "0.00 RUB"),
        (Decimal("-165497371.86"), "-165 497 371.86 RUB"),
    ],
)
def test_money_keeps_exact_cents(value: Decimal | None, expected: str) -> None:
    """Missing money is distinct from zero and negative amounts retain cents."""
    assert money(value) == expected


def test_undefined_and_signed_percentages() -> None:
    """Undefined or over-100% contributions must not be clamped or normalised."""
    assert percentage(None) == "—"
    assert percentage(Decimal("102.92")) == "102.92%"
    assert percentage(Decimal("-6.17")) == "-6.17%"


def test_revenue_chart_exact_hover_even_above_float_precision() -> None:
    """Amounts differing by one kopeck must remain distinct in hover labels."""
    response = RevenueResponse.model_validate(
        {
            "period": PERIOD,
            "paid_sales": "9007199254740993.01",
            "refunds": "0.01",
            "net_revenue": "9007199254740993.00",
            "comparison": None,
            "monthly": [
                {
                    "period": PERIOD,
                    "paid_sales": "9007199254740993.01",
                    "refunds": "0.01",
                    "net_revenue": "9007199254740993.00",
                }
            ],
        }
    )
    before = response.model_dump_json()
    figure = revenue_chart(response)

    assert figure.data[0].customdata[0] == "9 007 199 254 740 993.01 RUB"
    assert figure.data[2].customdata[0] == "9 007 199 254 740 993.00 RUB"
    assert "%{customdata}" in figure.data[0].hovertemplate
    assert figure.layout.xaxis.type == "category"
    assert response.model_dump_json() == before


def test_orders_chart_uses_api_counts_and_handles_no_orders() -> None:
    """A null AOV does not turn into an invented chart value."""
    response = OrdersResponse.model_validate(
        {
            "period": PERIOD,
            "paid_orders": 0,
            "average_order_value": None,
            "comparison": None,
            "monthly": [
                {"period": PERIOD, "paid_orders": 0, "average_order_value": None}
            ],
        }
    )
    figure = orders_chart(response)

    assert list(figure.data[0].y) == [0]
    assert figure.layout.xaxis.type == "category"
    assert response.average_order_value is None


def test_contribution_chart_preserves_sign_and_outsize_share() -> None:
    """Signed contributions are displayed as supplied, without reaggregation."""
    metrics = {
        "period": PERIOD,
        "paid_sales": "1.00",
        "refunds": "0.00",
        "net_revenue": "1.00",
        "paid_orders": 1,
        "average_order_value": "1.00",
    }
    item = {
        "name": "Pumps",
        "current_sales": "0.00",
        "current_refunds": "0.00",
        "previous_sales": "300000.00",
        "previous_refunds": "0.00",
        "current_net": "0.00",
        "previous_net": "300000.00",
        "delta": "-300000.00",
        "contribution_percent": "102.92",
    }
    response = ContributionsResponse.model_validate(
        {
            "dimension": "category",
            "current": metrics,
            "previous": metrics,
            "net_revenue": {
                "current": "17500.00",
                "previous": "309000.00",
                "absolute": "-291500.00",
                "percent": "-94.34",
            },
            "contributions": [item],
        }
    )
    figure = contribution_chart(response)

    assert list(figure.data[0].x) == [-300000.0]
    assert list(figure.data[0].customdata[0]) == ["-300 000.00 RUB", "102.92%"]
    assert response.contributions[0].contribution_percent == Decimal("102.92")
