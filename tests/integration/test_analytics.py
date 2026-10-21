"""Financial analytics match hand-calculated results on isolated PostgreSQL."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.models import Dimension, Period
from app.analytics.service import (
    compare_periods,
    contributions,
    monthly_metrics,
    summarize,
)
from app.db.models import Customer, Order, OrderItem, OrderStatus, Product, Refund
from app.db.sample import add_sample_data, msk

SEPTEMBER = Period.month(2026, 9)
OCTOBER = Period.month(2026, 10)


@pytest.fixture
def sample(db_session: Session) -> Session:
    """Reuse the documented sample while retaining the fixture's rollback."""
    add_sample_data(db_session)
    return db_session


def add_line(
    session: Session,
    sku: str,
    *,
    at: datetime | None = None,
    category: str = "Sensors",
    region: str = "North",
    price: str = "100.00",
    quantity: int = 1,
    discount: str = "0",
    status: OrderStatus = OrderStatus.PAID,
) -> OrderItem:
    """Persist an independent order with exact money and an explicit payment time."""
    moment = at or msk(2026, 9, 15, 12)
    item = OrderItem(
        order=Order(
            customer=Customer(name=sku, region=region, industry="Industry"),
            status=status,
            ordered_at=moment - timedelta(hours=1),
            paid_at=moment if status == OrderStatus.PAID else None,
        ),
        product=Product(sku=sku, name=sku, category=category, cost=Decimal("0.00")),
        quantity=quantity,
        unit_price=Decimal(price),
        discount=Decimal(discount),
    )
    session.add(item)
    session.flush()
    return item


def add_refund(
    session: Session, item: OrderItem, amount: str, *, at: datetime | None = None
) -> None:
    """Persist a partial refund without changing the source order's payment date."""
    session.add(
        Refund(
            order_item=item,
            amount=Decimal(amount),
            processed_at=at or msk(2026, 9, 20, 12),
        )
    )
    session.flush()


def test_sample_metrics_match_documented_months(sample: Session) -> None:
    """Sales use payment month; later refunds reduce their processing month."""
    september = summarize(sample, SEPTEMBER)
    october = summarize(sample, OCTOBER)

    assert september.period == SEPTEMBER
    assert (
        september.paid_sales,
        september.refunds,
        september.net_revenue,
        september.paid_orders,
        september.average_order_value,
    ) == (
        Decimal("310000.00"),
        Decimal("1000.00"),
        Decimal("309000.00"),
        2,
        Decimal("155000.00"),
    )
    assert (
        october.paid_sales,
        october.refunds,
        october.net_revenue,
        october.paid_orders,
        october.average_order_value,
    ) == (
        Decimal("18000.00"),
        Decimal("500.00"),
        Decimal("17500.00"),
        1,
        Decimal("18000.00"),
    )


def test_monthly_metrics_fill_gaps_and_clip_edge_months(sample: Session) -> None:
    """An arbitrary date range preserves every month, including empty segments."""
    period = Period(date(2026, 8, 15), date(2026, 11, 10))

    rows = monthly_metrics(sample, period)

    assert [row.period for row in rows] == [
        Period(date(2026, 8, 15), date(2026, 9, 1)),
        SEPTEMBER,
        OCTOBER,
        Period(date(2026, 11, 1), date(2026, 11, 10)),
    ]
    assert [row.net_revenue for row in rows] == [
        Decimal("0.00"),
        Decimal("309000.00"),
        Decimal("17500.00"),
        Decimal("0.00"),
    ]
    assert [row.paid_orders for row in rows] == [0, 2, 1, 0]
    assert rows[0].average_order_value is None
    assert rows[-1].average_order_value is None


def test_period_comparison_uses_sales_for_average_order_value(sample: Session) -> None:
    """The gross average check and percentage changes have independent known values."""
    result = compare_periods(sample, OCTOBER, SEPTEMBER)

    assert result.current.period == OCTOBER
    assert result.previous.period == SEPTEMBER
    assert result.net_revenue.current == Decimal("17500.00")
    assert result.net_revenue.previous == Decimal("309000.00")
    assert result.net_revenue.absolute == Decimal("-291500.00")
    assert result.net_revenue.percent == Decimal("-94.34")
    assert result.paid_sales.absolute == Decimal("-292000.00")
    assert result.paid_sales.percent == Decimal("-94.19")
    assert result.refunds.absolute == Decimal("-500.00")
    assert result.refunds.percent == Decimal("-50.00")
    assert result.paid_orders.absolute == -1
    assert result.paid_orders.percent == Decimal("-50.00")
    assert result.average_order_value is not None
    assert result.average_order_value.absolute == Decimal("-137000.00")
    assert result.average_order_value.percent == Decimal("-88.39")


@pytest.mark.parametrize("dimension", ["category", "region"])
def test_contribution_deltas_reconcile_with_total(
    sample: Session, dimension: Dimension
) -> None:
    """Dimension breakdowns account for the full total change without join inflation."""
    rows = contributions(sample, OCTOBER, SEPTEMBER, dimension=dimension)
    result = compare_periods(sample, OCTOBER, SEPTEMBER)

    assert sum((row.current_sales for row in rows), Decimal("0")) == Decimal("18000.00")
    assert sum((row.current_refunds for row in rows), Decimal("0")) == Decimal("500.00")
    assert sum((row.previous_sales for row in rows), Decimal("0")) == Decimal(
        "310000.00"
    )
    assert sum((row.previous_refunds for row in rows), Decimal("0")) == Decimal(
        "1000.00"
    )
    assert sum((row.delta for row in rows), Decimal("0")) == result.net_revenue.absolute
    assert [(row.delta, row.name) for row in rows] == sorted(
        (row.delta, row.name) for row in rows
    )


def test_category_breakdown_includes_refund_only_and_disappearing_groups(
    sample: Session,
) -> None:
    """October sensor refunds remain visible despite having no October sensor sale."""
    rows = contributions(sample, OCTOBER, SEPTEMBER, dimension="category")

    assert [
        (row.name, row.current_net, row.previous_net, row.delta) for row in rows
    ] == [
        ("Насосы", Decimal("0.00"), Decimal("300000.00"), Decimal("-300000.00")),
        ("Датчики", Decimal("-500.00"), Decimal("9000.00"), Decimal("-9500.00")),
        (
            "Запорная арматура",
            Decimal("18000.00"),
            Decimal("0.00"),
            Decimal("18000.00"),
        ),
    ]
    assert [row.contribution_percent for row in rows] == [
        Decimal("102.92"),
        Decimal("3.26"),
        Decimal("-6.17"),
    ]


def test_refunds_on_same_line_do_not_duplicate_sales_or_orders(
    db_session: Session,
) -> None:
    """Two partial refunds cannot multiply either the sold line or its paid order."""
    item = add_line(db_session, "PARTIAL")
    add_refund(db_session, item, "10.00")
    add_refund(db_session, item, "20.00")

    result = summarize(db_session, SEPTEMBER)
    (group,) = contributions(db_session, SEPTEMBER, OCTOBER, dimension="category")

    assert result.paid_sales == Decimal("100.00")
    assert result.refunds == Decimal("30.00")
    assert result.net_revenue == Decimal("70.00")
    assert result.paid_orders == 1
    assert result.average_order_value == Decimal("100.00")
    assert group.current_sales == Decimal("100.00")
    assert group.current_refunds == Decimal("30.00")


def test_each_discounted_line_is_rounded_before_aggregation(
    db_session: Session,
) -> None:
    """Two 0.045 RUB lines total 0.10 RUB after line-level HALF_UP rounding."""
    first = add_line(db_session, "ROUND-A", price="0.05", discount="0.1000")
    second_product = Product(
        sku="ROUND-B",
        name="Second rounded product",
        category="Sensors",
        cost=Decimal("0"),
    )
    db_session.add(
        OrderItem(
            order=first.order,
            product=second_product,
            quantity=1,
            unit_price=Decimal("0.05"),
            discount=Decimal("0.1000"),
        )
    )
    db_session.flush()

    result = summarize(db_session, SEPTEMBER)
    (group,) = contributions(db_session, SEPTEMBER, OCTOBER, dimension="category")

    assert result.paid_sales == Decimal("0.10")
    assert result.net_revenue == Decimal("0.10")
    assert result.paid_orders == 1
    assert result.average_order_value == Decimal("0.10")
    assert group.current_sales == Decimal("0.10")


def test_moscow_period_includes_start_and_excludes_end(db_session: Session) -> None:
    """Both payment and refund filters use exact Moscow midnight boundaries."""
    start = msk(2026, 9, 1, 0)
    end = msk(2026, 10, 1, 0)
    moments = [
        start - timedelta(microseconds=1),
        start,
        end - timedelta(microseconds=1),
        end,
    ]
    for index, moment in enumerate(moments):
        add_line(db_session, f"BOUNDARY-{index}", at=moment, price="100.00")
    older = add_line(db_session, "OLDER-REFUND", at=msk(2026, 8, 1, 12))
    for moment in moments:
        add_refund(db_session, older, "1.00", at=moment)

    result = summarize(db_session, SEPTEMBER)

    assert result.paid_sales == Decimal("200.00")
    assert result.refunds == Decimal("2.00")
    assert result.net_revenue == Decimal("198.00")
    assert result.paid_orders == 2


def test_empty_period_returns_zero_money_and_no_average(db_session: Session) -> None:
    """No payments and no refunds produce explicit zero totals and no average."""
    result = summarize(db_session, SEPTEMBER)

    assert result.paid_sales == Decimal("0.00")
    assert result.refunds == Decimal("0.00")
    assert result.net_revenue == Decimal("0.00")
    assert result.paid_orders == 0
    assert result.average_order_value is None
    assert contributions(db_session, SEPTEMBER, OCTOBER, dimension="category") == []


def test_zero_value_paid_order_counts_and_has_zero_average(db_session: Session) -> None:
    """A completed free order has a defined zero average, unlike an empty period."""
    add_line(db_session, "FREE", price="0.00")

    result = summarize(db_session, SEPTEMBER)

    assert result.paid_sales == Decimal("0.00")
    assert result.paid_orders == 1
    assert result.average_order_value == Decimal("0.00")


@pytest.mark.parametrize("status", [OrderStatus.PENDING, OrderStatus.CANCELLED])
def test_unpaid_orders_and_their_invalid_refunds_are_excluded(
    db_session: Session, status: OrderStatus
) -> None:
    """Analytics cannot count an unpaid line merely because a refund row exists."""
    item = add_line(db_session, "UNPAID", status=status)
    add_refund(db_session, item, "10.00")

    result = summarize(db_session, SEPTEMBER)

    assert result.paid_sales == Decimal("0.00")
    assert result.refunds == Decimal("0.00")
    assert result.net_revenue == Decimal("0.00")
    assert result.paid_orders == 0
    assert contributions(db_session, SEPTEMBER, OCTOBER, dimension="category") == []


def test_refund_only_period_has_negative_revenue_and_no_average(
    db_session: Session,
) -> None:
    """An earlier sale can yield a negative later period without any new paid order."""
    item = add_line(db_session, "REFUND-ONLY", at=msk(2026, 8, 15, 12))
    add_refund(db_session, item, "25.00")

    result = summarize(db_session, SEPTEMBER)

    assert result.paid_sales == Decimal("0.00")
    assert result.refunds == Decimal("25.00")
    assert result.net_revenue == Decimal("-25.00")
    assert result.paid_orders == 0
    assert result.average_order_value is None


@pytest.mark.parametrize("dimension", ["category", "region"])
def test_offsetting_group_changes_have_no_percentage_of_zero_delta(
    db_session: Session, dimension: Dimension
) -> None:
    """A disappearing and appearing group can cancel while both remain reported."""
    add_line(db_session, "OLD", category="Old", region="Old", price="100.00")
    add_line(
        db_session,
        "NEW",
        at=msk(2026, 10, 15, 12),
        category="New",
        region="New",
        price="100.00",
    )

    rows = contributions(db_session, OCTOBER, SEPTEMBER, dimension=dimension)

    assert [(row.name, row.delta) for row in rows] == [
        ("Old", Decimal("-100.00")),
        ("New", Decimal("100.00")),
    ]
    assert all(row.contribution_percent is None for row in rows)


def test_comparison_handles_zero_and_negative_baselines(db_session: Session) -> None:
    """Zero baselines have no percentage; negative baselines use their magnitude."""
    item = add_line(db_session, "NEGATIVE-BASELINE", at=msk(2026, 8, 15, 12))
    add_refund(db_session, item, "10.00")
    add_line(db_session, "POSITIVE-CURRENT", at=msk(2026, 10, 15, 12), price="5.00")

    result = compare_periods(db_session, OCTOBER, SEPTEMBER)

    assert result.net_revenue.previous == Decimal("-10.00")
    assert result.net_revenue.current == Decimal("5.00")
    assert result.net_revenue.absolute == Decimal("15.00")
    assert result.net_revenue.percent == Decimal("150.00")
    assert result.paid_sales.percent is None
    assert result.paid_orders.percent is None
    assert result.average_order_value is None


def test_analytics_do_not_autoflush_or_commit(sample: Session) -> None:
    """Read functions preserve pending rows and the caller's right to roll back."""
    invalid = Customer(name="", region="North", industry="Industry")
    sample.add(invalid)

    assert summarize(sample, SEPTEMBER).net_revenue == Decimal("309000.00")
    assert len(monthly_metrics(sample, SEPTEMBER)) == 1
    assert compare_periods(sample, OCTOBER, SEPTEMBER).net_revenue.absolute == Decimal(
        "-291500.00"
    )
    assert len(contributions(sample, OCTOBER, SEPTEMBER, dimension="category")) == 3
    assert invalid in sample.new
    assert invalid.id is None
    sample.expunge(invalid)
    sample.rollback()

    assert sample.scalar(select(func.count()).select_from(Order)) == 0
