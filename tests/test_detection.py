"""Detector fixtures check statistical semantics without labels or a database."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.analytics.anomaly_models import LinePoint, MonthlyPoint, StockPoint
from app.analytics.detection import (
    detect_monthly,
    detect_quantities,
    detect_stockouts,
    isolation_findings,
)
from app.analytics.models import Period


def monthly(
    index: int,
    quantity: str = "100",
    *,
    category: str = "Pumps",
    region: str | None = None,
    discount: str | None = "0.05",
    refund: str | None = "0.01",
) -> MonthlyPoint:
    """Build distinct months with exact synthetic totals and optional rates."""
    amount = Decimal(quantity)
    return MonthlyPoint(
        period=Period.month(2024 + index // 12, index % 12 + 1),
        category=category,
        region=region,
        paid_quantity=amount,
        paid_sales=amount * Decimal("10"),
        discount_rate=Decimal(discount) if discount is not None else None,
        refund_rate=Decimal(refund) if refund is not None else None,
        paid_lines=10,
    )


@pytest.mark.parametrize("quantity", ["1000", "0"])
def test_robust_z_flags_both_directions_with_leave_one_out_baseline(
    quantity: str,
) -> None:
    """A real extreme is compared against its peers, without contaminating itself."""
    points = [
        monthly(index, str(value))
        for index, value in enumerate([80, 90, 95, 100, 105, 110, 120])
    ]
    points.append(monthly(7, quantity))

    findings = detect_monthly(points)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "volume_shift"
    assert finding.period == points[-1].period
    assert finding.observed == Decimal(quantity)
    assert finding.baseline == Decimal("100")
    assert finding.score == Decimal("0.6745") * abs(Decimal(quantity) - 100) / 10


@pytest.mark.parametrize(
    ("quantity", "expected"), [("125", False), ("126", True), ("74", True)]
)
def test_flat_reference_uses_strict_meaningful_difference(
    quantity: str, expected: bool
) -> None:
    """The zero-MAD fallback requires more than a 25-percent quantity shift."""
    points = [monthly(index) for index in range(7)] + [monthly(7, quantity)]

    findings = detect_monthly(points)

    assert bool(findings) is expected
    if findings:
        assert findings[0].score is None
        assert findings[0].baseline == Decimal("100")


@pytest.mark.parametrize(("rate", "expected"), [("0.01", False), ("0.0101", True)])
def test_flat_rate_reference_has_one_percentage_point_floor(
    rate: str, expected: bool
) -> None:
    """A zero refund baseline does not flag an immaterial absolute difference."""
    points = [monthly(index, refund="0") for index in range(7)]
    points.append(monthly(7, refund=rate))

    findings = detect_monthly(points)

    assert bool(findings) is expected
    if findings:
        assert findings[0].kind == "refund_shift"
        assert findings[0].observed == Decimal(rate)


def test_monthly_groups_isolate_categories_regions_and_metrics() -> None:
    """Regional quantities are not category totals; discounts use regional peers."""
    points = [monthly(index) for index in range(8)]
    points += [monthly(index, "1000", category="Valves") for index in range(8)]
    points += [monthly(index, region="North") for index in range(7)]
    points += [monthly(7, "5000", region="North", discount="0.50")]
    points += [monthly(index, region="South", discount="0.50") for index in range(8)]

    findings = detect_monthly(points)

    assert len(findings) == 1
    assert findings[0].kind == "discount_shift"
    assert findings[0].entity == {"category": "Pumps", "region": "North"}
    assert findings[0].baseline == Decimal("0.05")
    assert detect_monthly(list(reversed(points))) == findings


def test_missing_rates_and_insufficient_peers_do_not_supply_baselines() -> None:
    """A missing metric is absent evidence, and six total points are insufficient."""
    assert (
        detect_monthly([monthly(index, str(1000**index)) for index in range(6)]) == []
    )
    points = [monthly(index, refund=None) for index in range(7)]
    points.append(monthly(7, refund="0.8"))
    assert detect_monthly(points) == []


def test_partial_months_are_not_compared_with_complete_months() -> None:
    """Clipped report edges cannot masquerade as volume or discount extremes."""
    partial = replace(
        monthly(7, "10000", refund="0.8"),
        period=Period(date(2024, 8, 5), date(2024, 9, 1)),
    )
    assert detect_monthly([monthly(index) for index in range(7)] + [partial]) == []
    regional = [monthly(index, region="North") for index in range(15)]
    partial_regional = replace(
        monthly(15, "10000", region="North", discount="0.8", refund="0.6"),
        period=Period(date(2025, 4, 1), date(2025, 4, 20)),
    )
    assert isolation_findings(regional + [partial_regional]) == []


@pytest.mark.parametrize("threshold", [Decimal("0"), Decimal("NaN")])
def test_monthly_rejects_invalid_threshold(threshold: Decimal) -> None:
    """Invalid configuration fails explicitly rather than hiding all signals."""
    with pytest.raises(ValueError, match="threshold"):
        detect_monthly([], threshold=threshold)


def test_monthly_rejects_nonpositive_history() -> None:
    """At least one other observation must define the reference distribution."""
    with pytest.raises(ValueError, match="min_history"):
        detect_monthly([], min_history=0)


def test_iqr_flags_only_high_quantity_and_keeps_one_day_evidence() -> None:
    """A flat category's large line is a real outlier with an exact Q3 baseline."""
    day = date(2024, 6, 7)
    points = [LinePoint(index, "Pumps", day, 1) for index in range(8)]
    points.append(LinePoint(99, "Pumps", day, 100))
    points.append(LinePoint(100, "Valves", day, 1000))

    findings = detect_quantities(points)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.entity == {"item_id": 99, "category": "Pumps"}
    assert finding.observed == Decimal("100")
    assert finding.baseline == Decimal("1")
    assert finding.period == Period(day, date(2024, 6, 8))
    assert detect_quantities(list(reversed(points))) == findings


def test_iqr_uses_exact_tukey_halves_and_requires_eight_observations() -> None:
    """Fractional quartiles stay Decimal and small groups cannot produce findings."""
    points = [
        LinePoint(index, "Pumps", date(2024, 1, 1), quantity)
        for index, quantity in enumerate([0, 1, 2, 3, 4, 5, 6, 100])
    ]
    findings = detect_quantities(points)
    assert len(findings) == 1
    assert findings[0].baseline == Decimal("5.5")
    assert detect_quantities(points[1:]) == []


def test_iqr_does_not_flag_zero_or_single_unit_in_flat_zero_series() -> None:
    """An absolute upper floor avoids treating one unit as a material extreme."""
    points = [LinePoint(index, "Pumps", date(2024, 1, 1), 0) for index in range(8)]
    assert (
        detect_quantities(points + [LinePoint(9, "Pumps", date(2024, 1, 1), 1)]) == []
    )


def test_stockouts_are_maximal_and_missing_dates_break_runs() -> None:
    """Two short runs cannot merge across an unobserved day or another product."""
    points = [
        StockPoint(1, date(2024, 1, day), 0)
        for day in [1, 2, 4, 5, 7, 8, 9, 10, 12, 13, 14]
    ]
    points += [StockPoint(1, date(2024, 1, 11), 2)]
    points += [StockPoint(2, date(2024, 1, day), 0) for day in [2, 3]]

    findings = detect_stockouts(list(reversed(points)))

    assert [finding.period for finding in findings] == [
        Period(date(2024, 1, 7), date(2024, 1, 11)),
        Period(date(2024, 1, 12), date(2024, 1, 15)),
    ]
    assert [finding.observed for finding in findings] == [Decimal("4"), Decimal("3")]
    assert all(finding.entity == {"product_id": 1} for finding in findings)
    assert all(
        finding.baseline is None and finding.score is None for finding in findings
    )


def test_stockout_minimum_is_configurable_and_validated() -> None:
    """The stock rule supports explicit run limits and rejects meaningless zero."""
    points = [StockPoint(1, date(2024, 1, 1), 0)]
    assert len(detect_stockouts(points, min_days=1)) == 1
    with pytest.raises(ValueError, match="min_days"):
        detect_stockouts(points, min_days=0)


def test_isolation_forest_finds_extreme_and_is_reproducible() -> None:
    """A fixed seed and canonical input order produce identical model evidence."""
    points = [monthly(index, region="North") for index in range(23)]
    points.append(monthly(23, "10000", region="North", discount="0.8", refund="0.6"))

    findings = isolation_findings(points)

    assert len(findings) == 1
    assert findings[0].period == points[-1].period
    assert findings[0].kind == "multivariate"
    assert findings[0].observed > 0
    assert findings[0].baseline == Decimal("0")
    assert findings[0].score == findings[0].observed
    assert isolation_findings(list(reversed(points))) == findings
    assert isolation_findings(points) == findings


def test_isolation_forest_skips_small_constant_and_unusable_series() -> None:
    """Missing rates and zero denominators cannot become invented numeric data."""
    constant = [monthly(index, region="North") for index in range(24)]
    assert isolation_findings(constant) == []
    assert isolation_findings(constant[:15] + [monthly(15, "10000")]) == []
    assert (
        isolation_findings([replace(point, discount_rate=None) for point in constant])
        == []
    )
    assert (
        isolation_findings(
            [replace(point, paid_sales=Decimal("0")) for point in constant]
        )
        == []
    )


def test_isolation_features_normalize_each_series_before_modeling() -> None:
    """A category's ordinary price and volume scale does not create model extremes."""
    points = [monthly(index, region="North") for index in range(16)]
    points += [
        monthly(index, "1000000", category="Valves", region="South")
        for index in range(16)
    ]
    assert isolation_findings(points) == []
