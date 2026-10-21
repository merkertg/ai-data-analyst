"""Reporting periods and percentage semantics do not depend on a database."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.analytics.models import Period, metric_change
from app.analytics.service import contributions, monthly_metrics


def test_calendar_month_and_moscow_midnights() -> None:
    """Moscow October starts while UTC still reports September."""
    period = Period.month(2026, 10)

    assert period == Period(date(2026, 10, 1), date(2026, 11, 1))
    assert period.start_at.astimezone(UTC) == datetime(2026, 9, 30, 21, tzinfo=UTC)
    assert period.end_at.astimezone(UTC) == datetime(2026, 10, 31, 21, tzinfo=UTC)


@pytest.mark.parametrize(
    ("year", "month", "end"),
    [(2024, 2, date(2024, 3, 1)), (2026, 12, date(2027, 1, 1))],
)
def test_calendar_month_handles_leap_year_and_december(
    year: int, month: int, end: date
) -> None:
    """Calendar boundaries use dates rather than a fixed number of days."""
    assert Period.month(year, month).end == end


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 9, 1), date(2026, 9, 1)),
        (date(2026, 10, 1), date(2026, 9, 1)),
        (datetime(2026, 9, 1), date(2026, 10, 1)),
        (date(2026, 9, 1), datetime(2026, 10, 1, tzinfo=UTC)),
    ],
)
def test_period_rejects_empty_reversed_or_datetime_boundaries(
    start: date, end: date
) -> None:
    """Datetime is a date subclass but cannot express a local date boundary."""
    with pytest.raises(ValueError):
        Period(start, end)


@pytest.mark.parametrize("month", [0, 13])
def test_period_rejects_invalid_calendar_month(month: int) -> None:
    """An invalid month is rejected before a database could be queried."""
    with pytest.raises(ValueError):
        Period.month(2026, month)


def test_reporting_period_is_immutable() -> None:
    """A report's period cannot silently change after its values are computed."""
    period = Period.month(2026, 9)
    with pytest.raises(FrozenInstanceError):
        period.start = date(2026, 8, 1)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("current", "previous", "absolute", "percent"),
    [
        ("150.00", "100.00", "50.00", "50.00"),
        ("0.00", "100.00", "-100.00", "-100.00"),
        ("-50.00", "-100.00", "50.00", "50.00"),
        ("-150.00", "-100.00", "-50.00", "-50.00"),
        ("3.00", "0.00", "3.00", None),
        ("0.00", "0.00", "0.00", None),
        ("1.00", "32.00", "-31.00", "-96.88"),
        ("33.00", "32.00", "1.00", "3.13"),
    ],
)
def test_metric_change_has_explicit_baseline_and_rounding_semantics(
    current: str, previous: str, absolute: str, percent: str | None
) -> None:
    """Zero is undefined, negative baselines use magnitude, and ties round away."""
    result = metric_change(Decimal(current), Decimal(previous))

    assert result.current == Decimal(current)
    assert result.previous == Decimal(previous)
    assert result.absolute == Decimal(absolute)
    assert result.percent == (Decimal(percent) if percent is not None else None)


def test_large_decimal_changes_preserve_every_monetary_digit() -> None:
    """Aggregates larger than Decimal's default precision retain exact deltas."""
    previous = Decimal("123456789012345678901234567890.01")
    current = Decimal("123456789012345678901234567890.02")

    result = metric_change(current, previous)

    assert result.absolute == Decimal("0.01")
    assert result.percent == Decimal("0.00")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_metric_change_rejects_nonfinite_money(value: str) -> None:
    """Nonfinite values cannot become monetary evidence in a comparison."""
    with pytest.raises(ValueError, match="finite"):
        metric_change(Decimal(value), Decimal("1.00"))


def test_monthly_limit_is_checked_before_database_access() -> None:
    """A 121-bucket request fails even when the session has no database bind."""
    with Session() as session, pytest.raises(ValueError, match="120"):
        monthly_metrics(session, Period(date(2016, 1, 1), date(2026, 1, 2)))


def test_dimension_allowlist_rejects_sql_text_before_database_access() -> None:
    """Caller-provided identifiers cannot become SQL syntax."""
    from app.analytics.models import Dimension

    period = Period.month(2026, 9)
    with Session() as session, pytest.raises(ValueError, match="Dimension"):
        contributions(session, period, period, cast(Dimension, "category; DROP TABLE"))
