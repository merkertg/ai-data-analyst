"""Independent reference answers computed with Pandas from the CSV bundle.

The oracle never touches PostgreSQL and never imports the analytics core: it
re-implements the metric rules from the exported files. If the SQL tools and
the oracle agree on every eval question, two separate implementations of the
same rules agree.

Money is handled as integer kopecks, so no float rounding is involved:
a line amount is quantity × price × (1 − discount), rounded half up to whole
kopecks, exactly like PostgreSQL ROUND(…, 2) on positive NUMERIC values.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path
from typing import Any

import pandas as pd

MOSCOW = "Europe/Moscow"
TWO_PLACES = Decimal("0.01")


def _kopecks(column: pd.Series) -> pd.Series:
    """'12345.67' → 1234567 exactly, via Decimal, never via float."""
    return column.map(lambda value: int(Decimal(value) * 100)).astype("int64")


def _moscow_dates(column: pd.Series) -> pd.Series:
    """ISO timestamps with offsets → Moscow calendar dates."""
    stamps = pd.to_datetime(column, utc=True).dt.tz_convert(MOSCOW)
    return stamps.dt.date


def money(kopecks: int) -> Decimal:
    """Integer kopecks → a two-place Decimal."""
    return (Decimal(kopecks) / 100).quantize(TWO_PLACES)


def percent(numerator: int, denominator: int) -> Decimal | None:
    """100 × a / |b| rounded half away from zero; None for a zero base."""
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 50
        value = Decimal(numerator) * 100 / abs(Decimal(denominator))
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def share(numerator: int, denominator: int) -> Decimal | None:
    """100 × a / b with the sign kept (contribution shares)."""
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 50
        value = Decimal(numerator) * 100 / Decimal(denominator)
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Totals:
    """Exact period totals in kopecks and the paid order count."""

    sales: int
    refunds: int
    orders: int

    @property
    def net(self) -> int:
        """Net revenue in kopecks."""
        return self.sales - self.refunds


class Oracle:
    """Answer metric questions from the six CSV files of one bundle."""

    def __init__(self, directory: Path) -> None:
        """Read the bundle once; every column is read as text first."""

        def read(name: str) -> pd.DataFrame:
            return pd.read_csv(
                directory / f"{name}.csv", dtype=str, keep_default_na=False
            )

        products = read("products")
        customers = read("customers")
        orders = read("orders")
        items = read("order_items")
        refunds = read("refunds")
        stock = read("inventory_snapshots")

        paid = orders[orders["status"] == "paid"].copy()
        paid["paid_on"] = _moscow_dates(paid["paid_at"])
        items["quantity"] = items["quantity"].astype("int64")
        price = _kopecks(items["unit_price"])
        discount = items["discount"].map(lambda value: int(Decimal(value) * 10000))
        # Half-up rounding to whole kopecks in integer arithmetic.
        items["amount"] = (
            items["quantity"] * price * (10000 - discount) + 5000
        ) // 10000

        lines = items.merge(
            paid[["id", "customer_id", "paid_on"]],
            left_on="order_id",
            right_on="id",
            suffixes=("", "_order"),
        )
        lines = lines.merge(
            products[["id", "sku", "name", "category"]],
            left_on="product_id",
            right_on="id",
            suffixes=("", "_product"),
        )
        lines = lines.merge(
            customers[["id", "region"]],
            left_on="customer_id",
            right_on="id",
            suffixes=("", "_customer"),
        )
        self.lines = lines[
            [
                "order_id",
                "quantity",
                "amount",
                "paid_on",
                "sku",
                "name",
                "category",
                "region",
            ]
        ]

        refunds["amount"] = _kopecks(refunds["amount"])
        refunds["processed_on"] = _moscow_dates(refunds["processed_at"])
        # Only refunds of lines of paid orders reduce revenue.
        refunded = refunds.merge(
            items[["id", "order_id", "product_id"]],
            left_on="order_item_id",
            right_on="id",
            suffixes=("", "_item"),
        )
        refunded = refunded[refunded["order_id"].isin(paid["id"])]
        refunded = refunded.merge(
            products[["id", "sku", "category"]],
            left_on="product_id",
            right_on="id",
            suffixes=("", "_product"),
        )
        refunded = refunded.merge(
            orders[["id", "customer_id"]],
            left_on="order_id",
            right_on="id",
            suffixes=("", "_order"),
        )
        refunded = refunded.merge(
            customers[["id", "region"]],
            left_on="customer_id",
            right_on="id",
            suffixes=("", "_customer"),
        )
        self.refunds = refunded[["amount", "processed_on", "sku", "category", "region"]]
        self.orders = paid[["id", "paid_on"]]

        stock["quantity"] = stock["quantity"].astype("int64")
        stock["snapshot_date"] = pd.to_datetime(stock["snapshot_date"]).dt.date
        self.stock = stock.merge(
            products[["id", "sku", "name", "category"]],
            left_on="product_id",
            right_on="id",
            suffixes=("", "_product"),
        )

    @staticmethod
    def _within(frame: pd.DataFrame, column: str, period: tuple[date, date]) -> Any:
        """Rows whose date falls in the half-open period."""
        return frame[(frame[column] >= period[0]) & (frame[column] < period[1])]

    def totals(
        self,
        period: tuple[date, date],
        column: str | None = None,
        value: str | None = None,
    ) -> Totals:
        """Sales, refunds and paid orders, optionally for one category or region."""
        lines = self._within(self.lines, "paid_on", period)
        refunds = self._within(self.refunds, "processed_on", period)
        if column is not None:
            lines = lines[lines[column] == value]
            refunds = refunds[refunds[column] == value]
        orders = (
            len(self._within(self.orders, "paid_on", period))
            if column is None
            else lines["order_id"].nunique()
        )
        return Totals(int(lines["amount"].sum()), int(refunds["amount"].sum()), orders)

    def group_deltas(
        self, column: str, period: tuple[date, date], previous: tuple[date, date]
    ) -> dict[str, int]:
        """Net revenue change per category or region, in kopecks."""
        names = set(self.lines[column]) | set(self.refunds[column])
        return {
            name: self.totals(period, column, name).net
            - self.totals(previous, column, name).net
            for name in names
        }

    def refunds_of(self, category: str, period: tuple[date, date]) -> tuple[int, int]:
        """Refund amount in kopecks and refund count for one category."""
        rows = self._within(self.refunds, "processed_on", period)
        rows = rows[rows["category"] == category]
        return int(rows["amount"].sum()), len(rows)

    def products_by_sales(
        self, period: tuple[date, date], category: str | None
    ) -> pd.DataFrame:
        """Products ordered by paid sales, then SKU, like the tool."""
        lines = self._within(self.lines, "paid_on", period)
        if category is not None:
            lines = lines[lines["category"] == category]
        grouped = lines.groupby(["sku", "name"], as_index=False)["amount"].sum()
        return grouped.sort_values(["amount", "sku"], ascending=[False, True])

    def stock_of(self, sku: str, period: tuple[date, date]) -> pd.DataFrame:
        """Snapshots of one product within the period, by date."""
        rows = self._within(self.stock, "snapshot_date", period)
        return rows[rows["sku"] == sku].sort_values("snapshot_date")

    def zero_stock_leader(
        self, category: str, period: tuple[date, date]
    ) -> tuple[str, str]:
        """SKU and name of the product with most zero-stock days in a category."""
        rows = self._within(self.stock, "snapshot_date", period)
        rows = rows[rows["category"] == category]
        zero = (
            rows.assign(zero=rows["quantity"] == 0)
            .groupby(["sku", "name"], as_index=False)["zero"]
            .sum()
        )
        best = zero.sort_values(["zero", "sku"], ascending=[False, True]).iloc[0]
        return str(best["sku"]), str(best["name"])

    def max_line_quantity(self, category: str, period: tuple[date, date]) -> int:
        """The largest paid line quantity of a category in the period."""
        lines = self._within(self.lines, "paid_on", period)
        return int(lines[lines["category"] == category]["quantity"].max())

    def coverage(self) -> tuple[date, date]:
        """First and last Moscow payment dates."""
        return min(self.orders["paid_on"]), max(self.orders["paid_on"])
