"""Bound, read-only PostgreSQL reports with exact NUMERIC money arithmetic."""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics.models import (
    Comparison,
    Contribution,
    Dimension,
    Period,
    PeriodMetrics,
    metric_change,
)

# Count orders independently of their lines. Aggregate sales and refunds on
# separate paths so several refunds cannot multiply an order's line amounts.
_METRICS_SQL = """
WITH periods(period_index, start_at, end_at) AS (VALUES {period_values}),
paid AS (
    SELECT span.period_index, COUNT(*) AS paid_orders
    FROM periods AS span
    JOIN orders AS o ON o.status = 'paid'
        AND o.paid_at >= span.start_at AND o.paid_at < span.end_at
    GROUP BY span.period_index
),
sales AS (
    SELECT span.period_index,
        SUM(ROUND(i.quantity * i.unit_price * (1 - i.discount), 2)) AS paid_sales
    FROM periods AS span
    JOIN orders AS o ON o.status = 'paid'
        AND o.paid_at >= span.start_at AND o.paid_at < span.end_at
    JOIN order_items AS i ON i.order_id = o.id
    GROUP BY span.period_index
),
refunded AS (
    SELECT span.period_index, SUM(r.amount) AS refunds
    FROM periods AS span
    JOIN refunds AS r ON r.processed_at >= span.start_at
        AND r.processed_at < span.end_at
    JOIN order_items AS i ON i.id = r.order_item_id
    JOIN orders AS o ON o.id = i.order_id AND o.status = 'paid'
    GROUP BY span.period_index
),
totals AS (
    SELECT span.period_index,
        COALESCE(s.paid_sales, CAST(0 AS NUMERIC)) AS paid_sales,
        COALESCE(r.refunds, CAST(0 AS NUMERIC)) AS refunds,
        COALESCE(p.paid_orders, 0) AS paid_orders
    FROM periods AS span
    LEFT JOIN paid AS p ON p.period_index = span.period_index
    LEFT JOIN sales AS s ON s.period_index = span.period_index
    LEFT JOIN refunded AS r ON r.period_index = span.period_index
)
SELECT period_index, paid_sales, refunds, paid_sales - refunds AS net_revenue,
    paid_orders, ROUND(paid_sales / NULLIF(paid_orders, 0), 2) AS average_order_value
FROM totals
ORDER BY period_index
"""

_CONTRIBUTIONS_SQL = """
WITH periods(period_index, start_at, end_at) AS (VALUES {period_values}),
events AS (
    SELECT span.period_index, {dimension_name} AS name,
        SUM(ROUND(i.quantity * i.unit_price * (1 - i.discount), 2)) AS paid_sales,
        CAST(0 AS NUMERIC) AS refunds
    FROM periods AS span
    JOIN orders AS o ON o.status = 'paid'
        AND o.paid_at >= span.start_at AND o.paid_at < span.end_at
    JOIN order_items AS i ON i.order_id = o.id
    {dimension_join}
    GROUP BY span.period_index, {dimension_name}
    UNION ALL
    SELECT span.period_index, {dimension_name} AS name,
        CAST(0 AS NUMERIC) AS paid_sales, SUM(r.amount) AS refunds
    FROM periods AS span
    JOIN refunds AS r ON r.processed_at >= span.start_at
        AND r.processed_at < span.end_at
    JOIN order_items AS i ON i.id = r.order_item_id
    JOIN orders AS o ON o.id = i.order_id AND o.status = 'paid'
    {dimension_join}
    GROUP BY span.period_index, {dimension_name}
),
totals AS (
    SELECT name,
        COALESCE(SUM(paid_sales) FILTER (WHERE period_index = 0), 0) AS current_sales,
        COALESCE(SUM(refunds) FILTER (WHERE period_index = 0), 0) AS current_refunds,
        COALESCE(SUM(paid_sales) FILTER (WHERE period_index = 1), 0) AS previous_sales,
        COALESCE(SUM(refunds) FILTER (WHERE period_index = 1), 0) AS previous_refunds
    FROM events
    GROUP BY name
),
changes AS (
    SELECT *, current_sales - current_refunds AS current_net,
        previous_sales - previous_refunds AS previous_net,
        current_sales - current_refunds - previous_sales + previous_refunds AS delta
    FROM totals
)
SELECT *, ROUND(100 * delta / NULLIF(SUM(delta) OVER (), 0), 2)
    AS contribution_percent
FROM changes
ORDER BY delta, name
"""


def _period_values(
    periods: Sequence[Period],
) -> tuple[str, dict[str, int | datetime]]:
    """Build trusted placeholder names while binding every interval boundary."""
    placeholders = []
    parameters: dict[str, int | datetime] = {}
    for index, period in enumerate(periods):
        placeholders.append(
            f"(CAST(:index_{index} AS INTEGER), "
            f"CAST(:start_{index} AS TIMESTAMPTZ), "
            f"CAST(:end_{index} AS TIMESTAMPTZ))"
        )
        parameters[f"index_{index}"] = index
        parameters[f"start_{index}"] = period.start_at
        parameters[f"end_{index}"] = period.end_at
    return ", ".join(placeholders), parameters


def _fetch_metrics(session: Session, periods: Sequence[Period]) -> list[PeriodMetrics]:
    """Read all requested periods in one PostgreSQL statement snapshot."""
    period_values, parameters = _period_values(periods)
    query = text(_METRICS_SQL.format(period_values=period_values))
    with session.no_autoflush:
        rows = session.execute(query, parameters).mappings().all()
    return [
        PeriodMetrics(
            period=period,
            paid_sales=cast(Decimal, row["paid_sales"]),
            refunds=cast(Decimal, row["refunds"]),
            net_revenue=cast(Decimal, row["net_revenue"]),
            paid_orders=cast(int, row["paid_orders"]),
            average_order_value=cast(Decimal | None, row["average_order_value"]),
        )
        for period, row in zip(periods, rows, strict=True)
    ]


def summarize(session: Session, period: Period) -> PeriodMetrics:
    """Read paid sales, processed refunds, order count and pre-refund AOV."""
    return _fetch_metrics(session, [period])[0]


def monthly_metrics(session: Session, period: Period) -> list[PeriodMetrics]:
    """Read up to 120 zero-filled calendar buckets clipped to the input period."""
    first_month = date(period.start.year, period.start.month, 1)
    last_date = date.fromordinal(period.end.toordinal() - 1)
    month_count = (
        (last_date.year - first_month.year) * 12
        + last_date.month
        - first_month.month
        + 1
    )
    if month_count > 120:
        raise ValueError("Monthly analytics supports at most 120 calendar months.")
    buckets = []
    month = first_month
    for _ in range(month_count):
        # A final partial month can end at date.max, whose following calendar
        # month cannot be represented by Python's date type.
        month_end = (
            period.end
            if (month.year, month.month) == (period.end.year, period.end.month)
            else Period.month(month.year, month.month).end
        )
        buckets.append(Period(max(period.start, month), min(period.end, month_end)))
        month = month_end
    return _fetch_metrics(session, buckets)


def compare_periods(session: Session, current: Period, previous: Period) -> Comparison:
    """Compare two intervals in one snapshot; unequal durations remain explicit."""
    current_metrics, previous_metrics = _fetch_metrics(session, [current, previous])
    current_aov = current_metrics.average_order_value
    previous_aov = previous_metrics.average_order_value
    return Comparison(
        current=current_metrics,
        previous=previous_metrics,
        paid_sales=metric_change(
            current_metrics.paid_sales, previous_metrics.paid_sales
        ),
        refunds=metric_change(current_metrics.refunds, previous_metrics.refunds),
        net_revenue=metric_change(
            current_metrics.net_revenue, previous_metrics.net_revenue
        ),
        paid_orders=metric_change(
            Decimal(current_metrics.paid_orders), Decimal(previous_metrics.paid_orders)
        ),
        average_order_value=(
            metric_change(current_aov, previous_aov)
            if current_aov is not None and previous_aov is not None
            else None
        ),
    )


def contributions(
    session: Session,
    current: Period,
    previous: Period,
    dimension: Dimension = "category",
) -> list[Contribution]:
    """Decompose net revenue changes, including refund-only dimension groups.

    Shares use each exact group delta divided by the exact overall net delta;
    they can be negative or exceed 100%, and are undefined for a zero total.
    Only the fixed allowlist controls SQL identifiers; all periods stay bound.
    """
    dimensions = {
        "category": ("p.category", "JOIN products AS p ON p.id = i.product_id"),
        "region": ("c.region", "JOIN customers AS c ON c.id = o.customer_id"),
    }
    if dimension not in dimensions:
        raise ValueError("Dimension must be 'category' or 'region'.")
    dimension_name, dimension_join = dimensions[dimension]
    period_values, parameters = _period_values([current, previous])
    query = text(
        _CONTRIBUTIONS_SQL.format(
            period_values=period_values,
            dimension_name=dimension_name,
            dimension_join=dimension_join,
        )
    )
    with session.no_autoflush:
        rows = session.execute(query, parameters).mappings().all()
    return [
        Contribution(
            name=cast(str, row["name"]),
            current_sales=cast(Decimal, row["current_sales"]),
            current_refunds=cast(Decimal, row["current_refunds"]),
            previous_sales=cast(Decimal, row["previous_sales"]),
            previous_refunds=cast(Decimal, row["previous_refunds"]),
            current_net=cast(Decimal, row["current_net"]),
            previous_net=cast(Decimal, row["previous_net"]),
            delta=cast(Decimal, row["delta"]),
            contribution_percent=cast(Decimal | None, row["contribution_percent"]),
        )
        for row in rows
    ]
