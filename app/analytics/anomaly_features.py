"""Build exact anomaly observations from business tables without answer keys."""

from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics.anomaly_models import FeatureSet, LinePoint, MonthlyPoint, StockPoint
from app.analytics.models import Period

# GROUPING SETS produces category and category-region series from independent
# sales/refund paths. Refund-only groups remain visible through the event union.
MONTHLY_SQL = """
WITH events AS (
    SELECT date_trunc('month', o.paid_at AT TIME ZONE 'Europe/Moscow')::date AS month,
        p.category, c.region, i.quantity::numeric AS paid_quantity,
        i.quantity * i.unit_price AS gross,
        ROUND(i.quantity * i.unit_price * (1-i.discount), 2) AS paid_sales,
        0::numeric AS refunds, 1 AS paid_lines
    FROM orders o JOIN order_items i ON i.order_id=o.id
    JOIN products p ON p.id=i.product_id JOIN customers c ON c.id=o.customer_id
    WHERE o.status='paid' AND o.paid_at >= :start_at AND o.paid_at < :end_at
    UNION ALL
    SELECT date_trunc('month', r.processed_at AT TIME ZONE 'Europe/Moscow')::date,
        p.category, c.region, 0::numeric, 0::numeric, 0::numeric, r.amount, 0
    FROM refunds r JOIN order_items i ON i.id=r.order_item_id
    JOIN orders o ON o.id=i.order_id AND o.status='paid'
    JOIN products p ON p.id=i.product_id JOIN customers c ON c.id=o.customer_id
    WHERE r.processed_at >= :start_at AND r.processed_at < :end_at
)
SELECT month, category, region, SUM(paid_quantity) AS paid_quantity,
    SUM(paid_sales) AS paid_sales, SUM(paid_lines) AS paid_lines,
    (SUM(gross)-SUM(paid_sales)) / NULLIF(SUM(gross),0) AS discount_rate,
    SUM(refunds) / NULLIF(SUM(paid_sales),0) AS refund_rate
FROM events GROUP BY GROUPING SETS ((month,category),(month,category,region))
ORDER BY category, region NULLS FIRST, month
"""
LINES_SQL = """
SELECT i.id AS item_id, p.category,
    (o.paid_at AT TIME ZONE 'Europe/Moscow')::date AS paid_on, i.quantity
FROM orders o JOIN order_items i ON i.order_id=o.id
JOIN products p ON p.id=i.product_id
WHERE o.status='paid' AND o.paid_at >= :start_at AND o.paid_at < :end_at
ORDER BY i.id
"""
STOCK_SQL = """
SELECT product_id, snapshot_date, quantity FROM inventory_snapshots
WHERE snapshot_date >= :start_date AND snapshot_date < :end_date
ORDER BY product_id, snapshot_date
"""


def read_features(session: Session, period: Period) -> FeatureSet:
    """Read three persisted result sets; callers control the snapshot transaction.

    Monthly ratios remain Decimal. Net discounts use rounded monetary lines,
    so a sub-kopeck nominal discount need not change the effective rate. Empty
    calendar groups are absent rather than fabricated as observations.
    """
    parameters = {"start_at": period.start_at, "end_at": period.end_at}
    with session.no_autoflush:
        monthly_rows = session.execute(text(MONTHLY_SQL), parameters).mappings().all()
        line_rows = session.execute(text(LINES_SQL), parameters).mappings().all()
        stock_rows = (
            session.execute(
                text(STOCK_SQL), {"start_date": period.start, "end_date": period.end}
            )
            .mappings()
            .all()
        )
    monthly = []
    for row in monthly_rows:
        month = cast(date, row["month"])
        end = (
            period.end
            if (month.year, month.month) == (period.end.year, period.end.month)
            else Period.month(month.year, month.month).end
        )
        monthly.append(
            MonthlyPoint(
                period=Period(max(month, period.start), min(end, period.end)),
                category=cast(str, row["category"]),
                region=cast(str | None, row["region"]),
                paid_quantity=cast(Decimal, row["paid_quantity"]),
                paid_sales=cast(Decimal, row["paid_sales"]),
                discount_rate=cast(Decimal | None, row["discount_rate"]),
                refund_rate=cast(Decimal | None, row["refund_rate"]),
                paid_lines=cast(int, row["paid_lines"]),
            )
        )
    return FeatureSet(
        monthly=monthly,
        lines=[
            LinePoint(
                item_id=cast(int, row["item_id"]),
                category=cast(str, row["category"]),
                paid_on=cast(date, row["paid_on"]),
                quantity=cast(int, row["quantity"]),
            )
            for row in line_rows
        ],
        stock=[
            StockPoint(
                product_id=cast(int, row["product_id"]),
                snapshot_date=cast(date, row["snapshot_date"]),
                quantity=cast(int, row["quantity"]),
            )
            for row in stock_rows
        ],
    )
