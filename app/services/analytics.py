"""Compose HTTP responses from the deterministic analytics core.

These functions only arrange results of app.analytics; every number is computed
by PostgreSQL and Decimal there. The caller provides one session, so all reads
of a response come from the same database snapshot.
"""

from sqlalchemy.orm import Session

from app.analytics.anomalies import build_anomaly_report
from app.analytics.models import Dimension, MetricChange
from app.analytics.service import (
    compare_periods,
    contributions,
    monthly_metrics,
    summarize,
)
from app.schemas.analytics import (
    AnomalyQuery,
    AnomalyReportResponse,
    ChangeOut,
    ComparisonQuery,
    ContributionOut,
    ContributionsResponse,
    MetricsOut,
    OptionalComparisonQuery,
    OrdersComparison,
    OrdersPoint,
    OrdersResponse,
    PeriodOut,
    RevenueComparison,
    RevenuePoint,
    RevenueResponse,
)


def _change(value: MetricChange | None) -> ChangeOut | None:
    """Convert an optional core change into its HTTP shape."""
    return None if value is None else ChangeOut.model_validate(value)


def revenue(session: Session, query: OptionalComparisonQuery) -> RevenueResponse:
    """Paid sales, refunds and net revenue with monthly buckets and a comparison."""
    period, previous = query.period(), query.previous()
    current = summarize(session, period)
    comparison = None
    if previous is not None:
        changes = compare_periods(session, period, previous)
        comparison = RevenueComparison(
            period=PeriodOut.model_validate(previous),
            paid_sales=ChangeOut.model_validate(changes.paid_sales),
            refunds=ChangeOut.model_validate(changes.refunds),
            net_revenue=ChangeOut.model_validate(changes.net_revenue),
        )
    return RevenueResponse(
        period=PeriodOut.model_validate(period),
        paid_sales=current.paid_sales,
        refunds=current.refunds,
        net_revenue=current.net_revenue,
        monthly=[
            RevenuePoint.model_validate(month)
            for month in monthly_metrics(session, period)
        ],
        comparison=comparison,
    )


def orders(session: Session, query: OptionalComparisonQuery) -> OrdersResponse:
    """Paid order count and pre-refund AOV with monthly buckets and a comparison."""
    period, previous = query.period(), query.previous()
    current = summarize(session, period)
    comparison = None
    if previous is not None:
        changes = compare_periods(session, period, previous)
        comparison = OrdersComparison(
            period=PeriodOut.model_validate(previous),
            paid_orders=ChangeOut.model_validate(changes.paid_orders),
            average_order_value=_change(changes.average_order_value),
        )
    return OrdersResponse(
        period=PeriodOut.model_validate(period),
        paid_orders=current.paid_orders,
        average_order_value=current.average_order_value,
        monthly=[
            OrdersPoint.model_validate(month)
            for month in monthly_metrics(session, period)
        ],
        comparison=comparison,
    )


def group_contributions(
    session: Session, query: ComparisonQuery, dimension: Dimension
) -> ContributionsResponse:
    """Overall net revenue change and each category's or region's share of it."""
    period, previous = query.period(), query.previous()
    changes = compare_periods(session, period, previous)
    return ContributionsResponse(
        dimension=dimension,
        current=MetricsOut.model_validate(changes.current),
        previous=MetricsOut.model_validate(changes.previous),
        net_revenue=ChangeOut.model_validate(changes.net_revenue),
        contributions=[
            ContributionOut.model_validate(group)
            for group in contributions(session, period, previous, dimension)
        ],
    )


def anomalies(session: Session, query: AnomalyQuery) -> AnomalyReportResponse:
    """Run the Stage 05 detector; it never reads the evaluation ground truth."""
    report = build_anomaly_report(session, query.period(), query.seed)
    return AnomalyReportResponse.model_validate(report)
