"""Agent tools on the documented sample: hand-checked answers, same as the API.

Sample (app/db/sample.py), Moscow time:
- September: pumps 2 × 100 000 − 10 % + 1 × 120 000 = 300 000.00 (3 units),
  sensors 5 × 2 000 = 10 000.00 with a 1 000.00 refund on 10 September;
- October: valves 4 × 4 500 = 18 000.00 paid at 01:30 on 1 October and a
  500.00 sensor refund on 2 October;
- stock on 30 September: pump 4, sensor 120, valve 0.
"""

import json
from contextlib import AbstractContextManager, nullcontext
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.agents.tools import ToolExecutor
from app.analytics.details import (
    data_coverage,
    refunds_by_category,
    stock_history,
    top_products,
)
from app.analytics.models import Period
from app.api.dependencies import read_session
from app.db.sample import add_sample_data
from app.llm.errors import ToolDataUnavailable
from app.main import app

SEPTEMBER, OCTOBER = Period.month(2026, 9), Period.month(2026, 10)


@pytest.fixture
def sample(db_session: Session) -> Session:
    """The Stage 02 sample in the rolled-back test transaction."""
    add_sample_data(db_session)
    return db_session


def executor(session: Session) -> ToolExecutor:
    """Tools that read the test transaction instead of opening new sessions."""

    def sessions() -> AbstractContextManager[Session]:
        return nullcontext(session)

    return ToolExecutor(sessions)


def test_coverage_reports_dates_and_names(sample: Session) -> None:
    """Order 5 is paid on 1 October in Moscow, so data ends there."""
    coverage = data_coverage(sample)

    assert (coverage.first_paid_on, coverage.last_paid_on) == (
        date(2026, 9, 5),
        date(2026, 10, 1),
    )
    assert coverage.paid_orders == 3
    assert (coverage.first_refund_on, coverage.last_refund_on) == (
        date(2026, 9, 10),
        date(2026, 10, 2),
    )
    assert coverage.first_stock_on == coverage.last_stock_on == date(2026, 9, 30)
    assert set(coverage.categories) == {"Насосы", "Датчики", "Запорная арматура"}
    assert set(coverage.regions) == {"Северо-Запад", "Юг"}


def test_top_products_by_paid_sales(sample: Session) -> None:
    """Refunds stay on their own path and do not multiply sales."""
    september = top_products(sample, SEPTEMBER, 5)
    october = top_products(sample, OCTOBER, 5)

    assert [
        (row.sku, row.quantity, row.paid_sales, row.refunds, row.net_revenue)
        for row in september
    ] == [
        ("PMP-100", 3, Decimal("300000.00"), Decimal("0"), Decimal("300000.00")),
        ("SNS-020", 5, Decimal("10000.00"), Decimal("1000.00"), Decimal("9000.00")),
    ]
    assert [(row.sku, row.paid_sales, row.net_revenue) for row in october] == [
        ("VLV-050", Decimal("18000.00"), Decimal("18000.00")),
        ("SNS-020", Decimal("0"), Decimal("-500.00")),
    ]
    assert [row.sku for row in top_products(sample, SEPTEMBER, 1, "Датчики")] == [
        "SNS-020"
    ]


def test_refunds_by_category(sample: Session) -> None:
    """September: 1 000.00 of 10 000.00 sensor sales is 10.00 %."""
    rows = refunds_by_category(sample, SEPTEMBER)

    assert [
        (row.category, row.refund_count, row.refunds, row.refund_rate_percent)
        for row in rows
    ] == [
        ("Датчики", 1, Decimal("1000.00"), Decimal("10.00")),
        ("Насосы", 0, Decimal("0"), Decimal("0.00")),
    ]
    october = refunds_by_category(sample, OCTOBER)
    sensors = next(row for row in october if row.category == "Датчики")
    assert (sensors.paid_sales, sensors.refund_rate_percent) == (Decimal("0"), None)


def test_stock_history_puts_stock_outs_first(sample: Session) -> None:
    """The valve had zero stock; days without a snapshot are not zero."""
    rows = stock_history(sample, SEPTEMBER, 5)

    assert [(row.sku, row.zero_stock_days, row.last_quantity) for row in rows] == [
        ("VLV-050", 1, 0),
        ("PMP-100", 0, 4),
        ("SNS-020", 0, 120),
    ]
    assert stock_history(sample, OCTOBER, 5) == []


def test_tool_results_equal_the_rest_api(sample: Session) -> None:
    """The agent sees exactly the numbers the API returns."""
    arguments = {
        "start": "2026-10-01",
        "end": "2026-11-01",
        "compare_start": "2026-09-01",
        "compare_end": "2026-10-01",
    }
    safe, result = executor(sample)("get_sales_by_category", json.dumps(arguments))

    def test_session() -> Session:
        return sample

    app.dependency_overrides[read_session] = test_session
    try:
        with TestClient(app) as client:
            api = client.get("/api/analytics/categories", params=arguments).json()
    finally:
        app.dependency_overrides.clear()

    assert safe == arguments
    assert result == {"ok": True, "data": api}
    assert result["data"]["net_revenue"]["absolute"] == "-291500.00"


def test_compare_periods_tool(sample: Session) -> None:
    """October vs September: net −291 500.00, one order fewer."""
    _, result = executor(sample)(
        "compare_periods",
        '{"start": "2026-10-01", "end": "2026-11-01", '
        '"compare_start": "2026-09-01", "compare_end": "2026-10-01"}',
    )

    changes = result["data"]["changes"]
    assert changes["net_revenue"]["absolute"] == "-291500.00"
    assert changes["paid_orders"]["absolute"] == "-1"
    assert changes["average_order_value"]["previous"] == "155000.00"


def test_anomaly_tool_filters_and_limits(sample: Session) -> None:
    """The tool reports totals even when it returns few or no findings."""
    _, result = executor(sample)(
        "detect_anomalies",
        '{"start": "2026-01-01", "end": "2026-11-01", "category": "Насосы", '
        '"limit": 3}',
    )

    data = result["data"]
    assert data["seed"] == 42
    assert data["category"] == "Насосы"
    assert len(data["findings"]) <= 3
    assert data["candidates_matching"] <= data["candidates_total"]


def test_database_failure_stops_the_run() -> None:
    """A broken connection is not a tool error the model could work around."""

    def broken() -> AbstractContextManager[Session]:
        raise OperationalError("SELECT 1", {}, Exception("down"))

    with pytest.raises(ToolDataUnavailable):
        ToolExecutor(broken)("get_data_coverage", "{}")
