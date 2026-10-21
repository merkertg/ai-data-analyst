"""Detail queries for the AI agent: coverage, products, refunds and stock.

Same rules as app.analytics.service: paid orders by Moscow payment date,
refunds by processing date, money as NUMERIC/Decimal, every value bound.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics.models import Period

_COVERAGE_SQL = """
SELECT
    (SELECT MIN((paid_at AT TIME ZONE 'Europe/Moscow')::date) FROM orders
        WHERE status = 'paid') AS first_paid_on,
    (SELECT MAX((paid_at AT TIME ZONE 'Europe/Moscow')::date) FROM orders
        WHERE status = 'paid') AS last_paid_on,
    (SELECT COUNT(*) FROM orders WHERE status = 'paid') AS paid_orders,
    (SELECT MIN((processed_at AT TIME ZONE 'Europe/Moscow')::date) FROM refunds)
        AS first_refund_on,
    (SELECT MAX((processed_at AT TIME ZONE 'Europe/Moscow')::date) FROM refunds)
        AS last_refund_on,
    (SELECT MIN(snapshot_date) FROM inventory_snapshots) AS first_stock_on,
    (SELECT MAX(snapshot_date) FROM inventory_snapshots) AS last_stock_on,
    (SELECT COALESCE(array_agg(DISTINCT category ORDER BY category), '{}')
        FROM products) AS categories,
    (SELECT COALESCE(array_agg(DISTINCT region ORDER BY region), '{}')
        FROM customers) AS regions
"""

# Sales and refunds are aggregated on separate paths, as in the core: several
# refunds of one line must not multiply that line's sales.
_PRODUCTS_SQL = """
WITH sales AS (
    SELECT i.product_id, SUM(i.quantity) AS quantity,
        SUM(ROUND(i.quantity * i.unit_price * (1 - i.discount), 2)) AS paid_sales
    FROM orders AS o
    JOIN order_items AS i ON i.order_id = o.id
    WHERE o.status = 'paid' AND o.paid_at >= :start_at AND o.paid_at < :end_at
    GROUP BY i.product_id
),
refunded AS (
    SELECT i.product_id, SUM(r.amount) AS refunds
    FROM refunds AS r
    JOIN order_items AS i ON i.id = r.order_item_id
    JOIN orders AS o ON o.id = i.order_id AND o.status = 'paid'
    WHERE r.processed_at >= :start_at AND r.processed_at < :end_at
    GROUP BY i.product_id
)
SELECT p.sku, p.name, p.category,
    COALESCE(s.quantity, 0) AS quantity,
    COALESCE(s.paid_sales, CAST(0 AS NUMERIC)) AS paid_sales,
    COALESCE(r.refunds, CAST(0 AS NUMERIC)) AS refunds,
    COALESCE(s.paid_sales, 0) - COALESCE(r.refunds, 0) AS net_revenue
FROM products AS p
LEFT JOIN sales AS s ON s.product_id = p.id
LEFT JOIN refunded AS r ON r.product_id = p.id
WHERE (s.product_id IS NOT NULL OR r.product_id IS NOT NULL)
    AND (CAST(:category AS TEXT) IS NULL OR p.category = CAST(:category AS TEXT))
ORDER BY paid_sales DESC, p.sku
LIMIT :limit
"""

_REFUNDS_SQL = """
WITH sales AS (
    SELECT p.category,
        SUM(ROUND(i.quantity * i.unit_price * (1 - i.discount), 2)) AS paid_sales
    FROM orders AS o
    JOIN order_items AS i ON i.order_id = o.id
    JOIN products AS p ON p.id = i.product_id
    WHERE o.status = 'paid' AND o.paid_at >= :start_at AND o.paid_at < :end_at
    GROUP BY p.category
),
refunded AS (
    SELECT p.category, COUNT(*) AS refund_count, SUM(r.amount) AS refunds
    FROM refunds AS r
    JOIN order_items AS i ON i.id = r.order_item_id
    JOIN orders AS o ON o.id = i.order_id AND o.status = 'paid'
    JOIN products AS p ON p.id = i.product_id
    WHERE r.processed_at >= :start_at AND r.processed_at < :end_at
    GROUP BY p.category
)
SELECT COALESCE(s.category, r.category) AS category,
    COALESCE(r.refund_count, 0) AS refund_count,
    COALESCE(r.refunds, CAST(0 AS NUMERIC)) AS refunds,
    COALESCE(s.paid_sales, CAST(0 AS NUMERIC)) AS paid_sales,
    ROUND(100 * COALESCE(r.refunds, 0) / NULLIF(s.paid_sales, 0), 2)
        AS refund_rate_percent
FROM sales AS s
FULL JOIN refunded AS r ON r.category = s.category
ORDER BY refunds DESC, category
"""

# Snapshot dates are plain local dates: no time zone conversion is needed.
_STOCK_SQL = """
WITH observed AS (
    SELECT s.product_id, COUNT(*) AS observed_days,
        COUNT(*) FILTER (WHERE s.quantity = 0) AS zero_stock_days,
        MIN(s.quantity) AS min_quantity, MAX(s.snapshot_date) AS last_snapshot_on
    FROM inventory_snapshots AS s
    WHERE s.snapshot_date >= :start AND s.snapshot_date < :end
    GROUP BY s.product_id
)
SELECT p.sku, p.name, p.category, o.observed_days, o.zero_stock_days,
    o.min_quantity, o.last_snapshot_on, last.quantity AS last_quantity
FROM observed AS o
JOIN products AS p ON p.id = o.product_id
JOIN inventory_snapshots AS last ON last.product_id = o.product_id
    AND last.snapshot_date = o.last_snapshot_on
WHERE CAST(:category AS TEXT) IS NULL OR p.category = CAST(:category AS TEXT)
ORDER BY o.zero_stock_days DESC, p.sku
LIMIT :limit
"""


@dataclass(frozen=True)
class DataCoverage:
    """Which dates and dimensions exist, so questions map to real periods."""

    first_paid_on: date | None
    last_paid_on: date | None
    paid_orders: int
    first_refund_on: date | None
    last_refund_on: date | None
    first_stock_on: date | None
    last_stock_on: date | None
    categories: list[str]
    regions: list[str]


@dataclass(frozen=True)
class ProductSales:
    """A product's paid quantity, exact sales, refunds and net revenue."""

    sku: str
    name: str
    category: str
    quantity: int
    paid_sales: Decimal
    refunds: Decimal
    net_revenue: Decimal


@dataclass(frozen=True)
class CategoryRefunds:
    """Refunds processed in a period next to sales paid in the same period."""

    category: str
    refund_count: int
    refunds: Decimal
    paid_sales: Decimal
    refund_rate_percent: Decimal | None


@dataclass(frozen=True)
class ProductStock:
    """Observed stock days; a missing snapshot is not assumed to be zero."""

    sku: str
    name: str
    category: str
    observed_days: int
    zero_stock_days: int
    min_quantity: int
    last_snapshot_on: date
    last_quantity: int


def data_coverage(session: Session) -> DataCoverage:
    """First and last dates of sales, refunds and stock, plus known names."""
    with session.no_autoflush:
        row = session.execute(text(_COVERAGE_SQL)).mappings().one()
    return DataCoverage(
        first_paid_on=row["first_paid_on"],
        last_paid_on=row["last_paid_on"],
        paid_orders=cast(int, row["paid_orders"]),
        first_refund_on=row["first_refund_on"],
        last_refund_on=row["last_refund_on"],
        first_stock_on=row["first_stock_on"],
        last_stock_on=row["last_stock_on"],
        categories=list(row["categories"]),
        regions=list(row["regions"]),
    )


def top_products(
    session: Session, period: Period, limit: int, category: str | None = None
) -> list[ProductSales]:
    """Products by paid sales in a period, optionally within one category.

    A product with only refunds in the period is listed with zero sales.
    """
    parameters = {
        "start_at": period.start_at,
        "end_at": period.end_at,
        "category": category,
        "limit": limit,
    }
    with session.no_autoflush:
        rows = session.execute(text(_PRODUCTS_SQL), parameters).mappings().all()
    return [
        ProductSales(
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            quantity=int(row["quantity"]),
            paid_sales=cast(Decimal, row["paid_sales"]),
            refunds=cast(Decimal, row["refunds"]),
            net_revenue=cast(Decimal, row["net_revenue"]),
        )
        for row in rows
    ]


def refunds_by_category(session: Session, period: Period) -> list[CategoryRefunds]:
    """Refund count, amount and rate per category, largest refunds first.

    The rate divides refunds processed in the period by sales paid in the same
    period. These are different cohorts of orders: the rate is a signal, not
    the share of this period's sales that will be returned.
    """
    parameters = {"start_at": period.start_at, "end_at": period.end_at}
    with session.no_autoflush:
        rows = session.execute(text(_REFUNDS_SQL), parameters).mappings().all()
    return [
        CategoryRefunds(
            category=row["category"],
            refund_count=cast(int, row["refund_count"]),
            refunds=cast(Decimal, row["refunds"]),
            paid_sales=cast(Decimal, row["paid_sales"]),
            refund_rate_percent=cast(Decimal | None, row["refund_rate_percent"]),
        )
        for row in rows
    ]


def stock_history(
    session: Session, period: Period, limit: int, category: str | None = None
) -> list[ProductStock]:
    """Products with the most zero-stock days in a period come first."""
    parameters = {
        "start": period.start,
        "end": period.end,
        "category": category,
        "limit": limit,
    }
    with session.no_autoflush:
        rows = session.execute(text(_STOCK_SQL), parameters).mappings().all()
    return [
        ProductStock(
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            observed_days=cast(int, row["observed_days"]),
            zero_stock_days=cast(int, row["zero_stock_days"]),
            min_quantity=cast(int, row["min_quantity"]),
            last_snapshot_on=row["last_snapshot_on"],
            last_quantity=cast(int, row["last_quantity"]),
        )
        for row in rows
    ]
