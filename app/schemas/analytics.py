"""HTTP shapes of analytics queries and results; money stays Decimal as JSON text."""

from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.analytics.models import Dimension, Period

# The same ten-year bound as monthly_metrics: a request cannot make the API
# build an unbounded monthly series.
MAX_MONTHS = 120
SEED_MAX = 2**32 - 1


def calendar_months(start: date, end: date) -> int:
    """Count calendar months touched by the half-open interval [start, end)."""
    last = date.fromordinal(end.toordinal() - 1)
    return (last.year - start.year) * 12 + last.month - start.month + 1


def check_interval(start: date, end: date, label: str) -> None:
    """Reject empty, reversed or over-long intervals with a readable message."""
    if start >= end:
        raise ValueError(f"{label}: start must be earlier than the exclusive end")
    if calendar_months(start, end) > MAX_MONTHS:
        raise ValueError(f"{label}: at most {MAX_MONTHS} calendar months are allowed")


class PeriodQuery(BaseModel):
    """Half-open Moscow date interval [start, end) taken from query parameters."""

    # Unknown query parameters are an error, not silently ignored typos.
    model_config = ConfigDict(extra="forbid")

    start: date = Field(description="Inclusive first date, Europe/Moscow")
    end: date = Field(description="Exclusive end date, Europe/Moscow")

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        """Check the main interval once, before any database access."""
        check_interval(self.start, self.end, "period")
        return self

    def period(self) -> Period:
        """The validated interval as the analytics core type."""
        return Period(self.start, self.end)


class OptionalComparisonQuery(PeriodQuery):
    """A period with an optional comparison period; both bounds or neither."""

    compare_start: date | None = Field(default=None, description="Comparison start")
    compare_end: date | None = Field(default=None, description="Comparison end")

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        """Accept no comparison or a complete, valid comparison interval."""
        if (self.compare_start is None) != (self.compare_end is None):
            raise ValueError("compare_start and compare_end must be given together")
        if self.compare_start is not None and self.compare_end is not None:
            check_interval(self.compare_start, self.compare_end, "comparison")
        return self

    def previous(self) -> Period | None:
        """The comparison interval, if requested."""
        if self.compare_start is None or self.compare_end is None:
            return None
        return Period(self.compare_start, self.compare_end)


class ComparisonQuery(PeriodQuery):
    """A period and the required period it is compared with."""

    compare_start: date = Field(description="Comparison start, inclusive")
    compare_end: date = Field(description="Comparison end, exclusive")

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        """Check the comparison interval with the same rules as the main one."""
        check_interval(self.compare_start, self.compare_end, "comparison")
        return self

    def previous(self) -> Period:
        """The comparison interval."""
        return Period(self.compare_start, self.compare_end)


class AnomalyQuery(PeriodQuery):
    """A detection period and the Isolation Forest seed."""

    seed: int = Field(default=42, ge=0, le=SEED_MAX, description="Forest seed")


class _FromAttributes(BaseModel):
    """Read values straight from the analytics dataclasses."""

    model_config = ConfigDict(from_attributes=True)


class PeriodOut(_FromAttributes):
    """A half-open date interval [start, end)."""

    start: date
    end: date


class MetricsOut(_FromAttributes):
    """Exact metrics of one period; AOV is before refunds, null without orders."""

    period: PeriodOut
    paid_sales: Decimal
    refunds: Decimal
    net_revenue: Decimal
    paid_orders: int
    average_order_value: Decimal | None


class ChangeOut(_FromAttributes):
    """Exact absolute change and a percentage of the absolute baseline."""

    previous: Decimal
    current: Decimal
    absolute: Decimal
    percent: Decimal | None


class RevenuePoint(_FromAttributes):
    """Revenue of one calendar month bucket."""

    period: PeriodOut
    paid_sales: Decimal
    refunds: Decimal
    net_revenue: Decimal


class RevenueComparison(BaseModel):
    """Revenue changes against the comparison period."""

    period: PeriodOut
    paid_sales: ChangeOut
    refunds: ChangeOut
    net_revenue: ChangeOut


class RevenueResponse(BaseModel):
    """Paid sales, processed refunds and net revenue for a period."""

    currency: Literal["RUB"] = "RUB"
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    period: PeriodOut
    paid_sales: Decimal
    refunds: Decimal
    net_revenue: Decimal
    monthly: list[RevenuePoint]
    comparison: RevenueComparison | None


class OrdersPoint(_FromAttributes):
    """Paid orders and average order value of one calendar month bucket."""

    period: PeriodOut
    paid_orders: int
    average_order_value: Decimal | None


class OrdersComparison(BaseModel):
    """Order count and AOV changes; AOV change is null if either side has none."""

    period: PeriodOut
    paid_orders: ChangeOut
    average_order_value: ChangeOut | None


class OrdersResponse(BaseModel):
    """Paid order count and average order value for a period."""

    currency: Literal["RUB"] = "RUB"
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    period: PeriodOut
    paid_orders: int
    average_order_value: Decimal | None
    monthly: list[OrdersPoint]
    comparison: OrdersComparison | None


class ContributionOut(_FromAttributes):
    """One category or region: net revenue in both periods and its share."""

    name: str
    current_sales: Decimal
    current_refunds: Decimal
    previous_sales: Decimal
    previous_refunds: Decimal
    current_net: Decimal
    previous_net: Decimal
    delta: Decimal
    contribution_percent: Decimal | None


class ContributionsResponse(BaseModel):
    """Both periods, the overall net change and each group's signed share."""

    currency: Literal["RUB"] = "RUB"
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    dimension: Dimension
    current: MetricsOut
    previous: MetricsOut
    net_revenue: ChangeOut
    contributions: list[ContributionOut]


class FindingOut(_FromAttributes):
    """A candidate to investigate with exact evidence, not a causal claim."""

    id: str
    method: str
    kind: str
    period: PeriodOut
    entity: dict[str, str | int]
    metric: str
    observed: Decimal
    baseline: Decimal | None
    score: Decimal | None


class AnomalyReportResponse(_FromAttributes):
    """Detector output for a period; it never contains evaluation labels."""

    schema_version: int
    period: PeriodOut
    seed: int
    observations: dict[str, int]
    configuration: dict[str, str | int]
    finding_count: int
    findings: list[FindingOut]
