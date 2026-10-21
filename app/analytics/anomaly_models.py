"""Exact observations and structured evidence for exploratory anomaly detection."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.analytics.models import Period


@dataclass(frozen=True)
class MonthlyPoint:
    """One observed category or category-region month; absent ratios stay None."""

    period: Period
    category: str
    region: str | None
    paid_quantity: Decimal
    paid_sales: Decimal
    discount_rate: Decimal | None
    refund_rate: Decimal | None
    paid_lines: int


@dataclass(frozen=True)
class LinePoint:
    """A paid line's non-monetary quantity and local payment date."""

    item_id: int
    category: str
    paid_on: date
    quantity: int


@dataclass(frozen=True)
class StockPoint:
    """A daily stock observation; missing dates are not assumed to be zero."""

    product_id: int
    snapshot_date: date
    quantity: int


@dataclass(frozen=True)
class FeatureSet:
    """Persisted database observations; no evaluation labels are included."""

    monthly: list[MonthlyPoint]
    lines: list[LinePoint]
    stock: list[StockPoint]


@dataclass(frozen=True)
class Finding:
    """A candidate to investigate, with exact values rather than a causal claim."""

    id: str
    method: str
    kind: str
    period: Period
    entity: dict[str, str | int]
    metric: str
    observed: Decimal
    baseline: Decimal | None
    score: Decimal | None
