"""Exact metric values and Moscow reporting periods shared by analytics tools."""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Literal, Self
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")
Dimension = Literal["category", "region"]
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Period:
    """A half-open interval of local dates, converted to Moscow midnights."""

    start: date
    end: date

    def __post_init__(self) -> None:
        """Reject ambiguous datetime inputs and empty or reversed intervals."""
        for value in (self.start, self.end):
            if not isinstance(value, date) or isinstance(value, datetime):
                raise ValueError("Period boundaries must be dates, not datetimes.")
        if self.start >= self.end:
            raise ValueError("Period start must be earlier than its exclusive end.")

    @classmethod
    def month(cls, year: int, month: int) -> Self:
        """Create a complete calendar month, including the December rollover."""
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return cls(start, end)

    @property
    def start_at(self) -> datetime:
        """Return the inclusive Moscow midnight used as a bound SQL parameter."""
        return datetime.combine(self.start, time.min, tzinfo=MOSCOW)

    @property
    def end_at(self) -> datetime:
        """Return the exclusive Moscow midnight used as a bound SQL parameter."""
        return datetime.combine(self.end, time.min, tzinfo=MOSCOW)


@dataclass(frozen=True)
class PeriodMetrics:
    """Exact RUB metrics; AOV is before refunds and absent without paid orders."""

    period: Period
    paid_sales: Decimal
    refunds: Decimal
    net_revenue: Decimal
    paid_orders: int
    average_order_value: Decimal | None


@dataclass(frozen=True)
class MetricChange:
    """Absolute change and a rounded percentage relative to the baseline size."""

    previous: Decimal
    current: Decimal
    absolute: Decimal
    percent: Decimal | None


def metric_change(current: Decimal, previous: Decimal) -> MetricChange:
    """Use an absolute denominator so increasing a negative baseline is positive.

    A zero baseline has no defined relative percentage. The absolute change is
    kept exact; only its displayed percentage is rounded, with ties away from
    zero, matching PostgreSQL ROUND on NUMERIC values.
    """
    # Allow large SQL aggregates without losing significant monetary digits in
    # Python's default 28-digit context before the percentage is rounded.
    current_tuple = current.as_tuple()
    previous_tuple = previous.as_tuple()
    current_exponent = current_tuple.exponent
    previous_exponent = previous_tuple.exponent
    if not isinstance(current_exponent, int) or not isinstance(previous_exponent, int):
        raise ValueError("Metric changes require finite Decimal values.")
    precision = max(len(current_tuple.digits), len(previous_tuple.digits))
    exponent_gap = abs(current_exponent - previous_exponent)
    with localcontext() as context:
        context.prec = max(28, precision + exponent_gap + 8)
        absolute = current - previous
        percent = (
            (absolute / abs(previous) * HUNDRED).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            if previous
            else None
        )
    return MetricChange(previous, current, absolute, percent)


@dataclass(frozen=True)
class Comparison:
    """Two period snapshots and their independently calculated metric changes."""

    current: PeriodMetrics
    previous: PeriodMetrics
    paid_sales: MetricChange
    refunds: MetricChange
    net_revenue: MetricChange
    paid_orders: MetricChange
    average_order_value: MetricChange | None


@dataclass(frozen=True)
class Contribution:
    """A dimension's exact net change and share of the overall net change."""

    name: str
    current_sales: Decimal
    current_refunds: Decimal
    previous_sales: Decimal
    previous_refunds: Decimal
    current_net: Decimal
    previous_net: Decimal
    delta: Decimal
    contribution_percent: Decimal | None
