"""Deterministic retrospective anomaly rules and a reproducible model signal."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from sklearn.ensemble import IsolationForest

from app.analytics.anomaly_models import Finding, LinePoint, MonthlyPoint, StockPoint
from app.analytics.models import Period

ZERO = Decimal("0")
ONE = Decimal("1")
MAD_SCALE = Decimal("0.6745")


def _median(values: Sequence[Decimal]) -> Decimal:
    """Calculate an exact median without converting Decimal values to floats."""
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _monthly_id(method: str, kind: str, point: MonthlyPoint) -> str:
    """Keep monthly finding identifiers stable across input ordering and reruns."""
    return ":".join(
        (method, kind, point.category, point.region or "all", str(point.period.start))
    )


def _entity(point: MonthlyPoint) -> dict[str, str | int]:
    """Name only the dimensions present in the corresponding SQL observation."""
    entity: dict[str, str | int] = {"category": point.category}
    if point.region is not None:
        entity["region"] = point.region
    return entity


def _complete_month(point: MonthlyPoint) -> bool:
    """Keep clipped report edges out of comparisons against complete months."""
    return point.period == Period.month(
        point.period.start.year, point.period.start.month
    )


def detect_monthly(
    points: Sequence[MonthlyPoint],
    min_history: int = 6,
    threshold: Decimal = Decimal("6"),
) -> list[Finding]:
    """Find two-sided shifts against other months in the same dimension series.

    This is a retrospective leave-one-out baseline, not an online forecast. A
    flat reference series has no defined robust z-score, so an explicit relative
    and absolute floor replaces division by zero for those series.
    """
    if min_history < 1:
        raise ValueError("min_history must be positive.")
    if not threshold.is_finite() or threshold <= ZERO:
        raise ValueError("threshold must be a positive finite Decimal.")
    groups: dict[tuple[str, str | None], list[MonthlyPoint]] = defaultdict(list)
    for point in points:
        if _complete_month(point):
            groups[point.category, point.region].append(point)

    findings: list[Finding] = []
    for group in groups.values():
        metrics = (
            (("paid_quantity", "volume_shift"), ("refund_rate", "refund_shift"))
            if group[0].region is None
            else (("discount_rate", "discount_shift"),)
        )
        for metric, kind in metrics:
            for index, point in enumerate(group):
                value: Decimal | None = getattr(point, metric)
                if value is None:
                    continue
                reference = [
                    other_value
                    for other_index, other in enumerate(group)
                    if other_index != index
                    and (other_value := getattr(other, metric)) is not None
                ]
                if len(reference) < min_history:
                    continue
                baseline = _median(reference)
                deviation = abs(value - baseline)
                mad = _median([abs(item - baseline) for item in reference])
                score = MAD_SCALE * deviation / mad if mad else None
                floor = ONE if metric == "paid_quantity" else Decimal("0.01")
                unusual = (
                    score >= threshold
                    if score is not None
                    else deviation > max(abs(baseline) * Decimal("0.25"), floor)
                )
                if unusual:
                    findings.append(
                        Finding(
                            id=_monthly_id("robust_zscore", kind, point),
                            method="robust_zscore",
                            kind=kind,
                            period=point.period,
                            entity=_entity(point),
                            metric=metric,
                            observed=value,
                            baseline=baseline,
                            score=score,
                        )
                    )
    return sorted(findings, key=lambda finding: finding.id)


def detect_quantities(points: Sequence[LinePoint]) -> list[Finding]:
    """Flag high order-line quantities using category-specific outer IQR fences."""
    groups: dict[str, list[LinePoint]] = defaultdict(list)
    for point in points:
        groups[point.category].append(point)
    findings: list[Finding] = []
    for category, group in groups.items():
        if len(group) < 8:
            continue
        values = sorted(Decimal(point.quantity) for point in group)
        midpoint = len(values) // 2
        lower = _median(values[:midpoint])
        # Tukey's hinges exclude the central observation for an odd sample size.
        upper = _median(values[midpoint + len(values) % 2 :])
        fence = max(upper + Decimal("3") * (upper - lower), ONE)
        for point in group:
            observed = Decimal(point.quantity)
            if observed <= fence:
                continue
            findings.append(
                Finding(
                    id=f"iqr:quantity_outlier:{category}:{point.item_id}",
                    method="iqr",
                    kind="quantity_outlier",
                    period=Period(point.paid_on, point.paid_on + timedelta(days=1)),
                    entity={"item_id": point.item_id, "category": category},
                    metric="quantity",
                    observed=observed,
                    baseline=upper,
                    score=None,
                )
            )
    return sorted(findings, key=lambda finding: finding.id)


def detect_stockouts(points: Sequence[StockPoint], min_days: int = 3) -> list[Finding]:
    """Report maximal consecutive zero-stock runs; missing dates break a run."""
    if min_days < 1:
        raise ValueError("min_days must be positive.")
    groups: dict[int, list[StockPoint]] = defaultdict(list)
    for point in points:
        groups[point.product_id].append(point)
    findings: list[Finding] = []

    def append_run(product_id: int, run: list[StockPoint]) -> None:
        """Emit one finding for the entire maximal run, including trailing runs."""
        if len(run) < min_days:
            return
        period = Period(run[0].snapshot_date, run[-1].snapshot_date + timedelta(days=1))
        findings.append(
            Finding(
                id=f"stock_rule:stockout:{product_id}:{period.start}",
                method="stock_rule",
                kind="stockout",
                period=period,
                entity={"product_id": product_id},
                metric="zero_stock_days",
                observed=Decimal(len(run)),
                baseline=None,
                score=None,
            )
        )

    for product_id, group in groups.items():
        run: list[StockPoint] = []
        for point in sorted(group, key=lambda item: item.snapshot_date):
            if run and point.snapshot_date != run[-1].snapshot_date + timedelta(days=1):
                append_run(product_id, run)
                run = []
            if point.quantity == 0:
                run.append(point)
            else:
                append_run(product_id, run)
                run = []
        append_run(product_id, run)
    return sorted(findings, key=lambda finding: finding.id)


def isolation_findings(points: Sequence[MonthlyPoint], seed: int = 42) -> list[Finding]:
    """Add reproducible unsupervised signals using only dimensionless features.

    Monetary aggregates stay Decimal. Only ratios to each series' median and
    already dimensionless rates cross the estimator's floating-point boundary.
    Series with nonpositive median denominators cannot supply valid ratios.
    """
    groups: dict[tuple[str, str], list[MonthlyPoint]] = defaultdict(list)
    for point in points:
        if (
            _complete_month(point)
            and point.region is not None
            and point.discount_rate is not None
            and point.refund_rate is not None
        ):
            groups[point.category, point.region].append(point)
    eligible: list[MonthlyPoint] = []
    features: list[list[float]] = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda point: point.period.start)
        median_quantity = _median([point.paid_quantity for point in group])
        median_sales = _median([point.paid_sales for point in group])
        if median_quantity <= ZERO or median_sales <= ZERO:
            continue
        for point in group:
            # The group filter guarantees both rates are present here.
            assert point.discount_rate is not None and point.refund_rate is not None
            eligible.append(point)
            features.append(
                [
                    float(point.paid_quantity / median_quantity),
                    float(point.paid_sales / median_sales),
                    float(point.discount_rate),
                    float(point.refund_rate),
                ]
            )
    if len(features) < 16 or all(row == features[0] for row in features):
        return []
    estimator = IsolationForest(
        n_estimators=100,
        random_state=seed,
        n_jobs=1,
        contamination="auto",
        max_samples="auto",
    )
    decisions = estimator.fit(features).decision_function(features)
    findings: list[Finding] = []
    for point, decision in zip(eligible, decisions, strict=True):
        if decision >= 0:
            continue
        score = Decimal(str(-decision))
        findings.append(
            Finding(
                id=_monthly_id("isolation_forest", "multivariate", point),
                method="isolation_forest",
                kind="multivariate",
                period=point.period,
                entity=_entity(point),
                metric="anomaly_score",
                observed=score,
                baseline=ZERO,
                score=score,
            )
        )
    return sorted(findings, key=lambda finding: finding.id)
