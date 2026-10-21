"""The HTTP API returns the same exact numbers as the analytics core.

Routes get the rolled-back test session through dependency overrides, so every
test sees only its own rows on the isolated *_test database.
"""

import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from psycopg import errors
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.analytics.anomalies import build_anomaly_report
from app.analytics.models import Period
from app.analytics.service import compare_periods, contributions, summarize
from app.api import dependencies
from app.api.dependencies import read_session, write_session
from app.db.models import Customer, Order, OrderItem, OrderStatus, Product, Report
from app.db.sample import add_sample_data, msk
from app.main import app

SEPTEMBER = {"start": "2026-09-01", "end": "2026-10-01"}
OCTOBER_VS_SEPTEMBER = {
    "start": "2026-10-01",
    "end": "2026-11-01",
    "compare_start": "2026-09-01",
    "compare_end": "2026-10-01",
}


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """API client whose read and write sessions are the test transaction."""

    def test_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[read_session] = test_session
    app.dependency_overrides[write_session] = test_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample(db_session: Session) -> Session:
    """The documented Stage 02 sample: 5 orders, 2 refunds, known answers."""
    add_sample_data(db_session)
    return db_session


def test_revenue_matches_hand_calculation(client: TestClient, sample: Session) -> None:
    """September: 310 000.00 sales, 1 000.00 refunds, 309 000.00 net."""
    body = client.get("/api/metrics/revenue", params=SEPTEMBER).json()

    assert (body["paid_sales"], body["refunds"], body["net_revenue"]) == (
        "310000.00",
        "1000.00",
        "309000.00",
    )
    assert body["currency"] == "RUB"
    assert body["timezone"] == "Europe/Moscow"
    assert body["comparison"] is None
    assert [month["period"] for month in body["monthly"]] == [
        {"start": "2026-09-01", "end": "2026-10-01"}
    ]


def test_revenue_comparison_october_vs_september(
    client: TestClient, sample: Session
) -> None:
    """October vs September: −291 500.00 net, −94.34 %."""
    body = client.get("/api/metrics/revenue", params=OCTOBER_VS_SEPTEMBER).json()

    net = body["comparison"]["net_revenue"]
    assert (net["previous"], net["current"]) == ("309000.00", "17500.00")
    assert (net["absolute"], net["percent"]) == ("-291500.00", "-94.34")
    assert body["comparison"]["period"] == {"start": "2026-09-01", "end": "2026-10-01"}


def test_orders_and_average_order_value(client: TestClient, sample: Session) -> None:
    """Two paid September orders, AOV 155 000.00; October has one at 18 000.00."""
    body = client.get("/api/metrics/orders", params=OCTOBER_VS_SEPTEMBER).json()

    assert (body["paid_orders"], body["average_order_value"]) == (1, "18000.00")
    assert body["comparison"]["paid_orders"]["absolute"] == "-1"
    assert body["comparison"]["average_order_value"]["previous"] == "155000.00"


def test_empty_period_has_zero_money_and_no_average(client: TestClient) -> None:
    """No data: zeros, and AOV is null rather than a division by zero."""
    body = client.get("/api/metrics/orders", params=SEPTEMBER).json()

    assert (body["paid_orders"], body["average_order_value"]) == (0, None)


def test_category_contributions(client: TestClient, sample: Session) -> None:
    """Pumps −300 000.00 (102.92 %), sensors −9 500.00, valves +18 000.00."""
    body = client.get("/api/analytics/categories", params=OCTOBER_VS_SEPTEMBER).json()

    assert body["dimension"] == "category"
    assert body["net_revenue"]["absolute"] == "-291500.00"
    assert [
        (group["name"], group["delta"], group["contribution_percent"])
        for group in body["contributions"]
    ] == [
        ("Насосы", "-300000.00", "102.92"),
        ("Датчики", "-9500.00", "3.26"),
        ("Запорная арматура", "18000.00", "-6.17"),
    ]


def test_region_deltas_reconcile_with_total(
    client: TestClient, sample: Session
) -> None:
    """Regional deltas add up exactly to the overall net revenue change."""
    body = client.get("/api/analytics/regions", params=OCTOBER_VS_SEPTEMBER).json()

    deltas = sum(Decimal(group["delta"]) for group in body["contributions"])
    assert deltas == Decimal(body["net_revenue"]["absolute"])
    assert {group["name"] for group in body["contributions"]} == {
        "Северо-Запад",
        "Юг",
    }


def test_api_equals_analytics_core(client: TestClient, sample: Session) -> None:
    """The HTTP layer adds no arithmetic: numbers equal the core functions."""
    current, previous = Period.month(2026, 10), Period.month(2026, 9)
    core = compare_periods(sample, current, previous)
    groups = contributions(sample, current, previous, "category")

    body = client.get("/api/analytics/categories", params=OCTOBER_VS_SEPTEMBER).json()

    assert Decimal(body["current"]["net_revenue"]) == core.current.net_revenue
    assert Decimal(body["previous"]["paid_sales"]) == core.previous.paid_sales
    assert [Decimal(group["delta"]) for group in body["contributions"]] == [
        group.delta for group in groups
    ]
    revenue = client.get("/api/metrics/revenue", params=SEPTEMBER).json()
    assert Decimal(revenue["net_revenue"]) == summarize(sample, previous).net_revenue


def test_anomalies_route_returns_detector_report(
    client: TestClient, sample: Session
) -> None:
    """The route returns the Stage 05 report for the same snapshot and seed."""
    params = {"start": "2026-01-01", "end": "2026-10-01", "seed": "7"}
    body = client.get("/api/analytics/anomalies", params=params).json()
    core = build_anomaly_report(
        sample, Period(date(2026, 1, 1), date(2026, 10, 1)), seed=7
    )

    assert body["seed"] == 7
    assert body["finding_count"] == len(body["findings"]) == core["finding_count"]
    assert body["observations"] == core["observations"]
    assert "ground_truth" not in str(body)


def test_report_round_trip(client: TestClient, sample: Session) -> None:
    """POST stores a snapshot; GET returns exactly the stored result."""
    created = client.post(
        "/api/reports",
        json={"kind": "comparison", **OCTOBER_VS_SEPTEMBER, "dimension": "category"},
    )

    assert created.status_code == 201
    report = created.json()
    assert created.headers["location"] == f"/api/reports/{report['id']}"
    assert report["kind"] == "comparison"
    assert report["parameters"]["dimension"] == "category"
    assert report["result"]["net_revenue"]["absolute"] == "-291500.00"

    fetched = client.get(f"/api/reports/{report['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == report


def test_report_is_a_snapshot(client: TestClient, sample: Session) -> None:
    """New sales change live analytics but not an already saved report."""
    report = client.post(
        "/api/reports", json={"kind": "comparison", **OCTOBER_VS_SEPTEMBER}
    ).json()
    sample.add(
        OrderItem(
            order=Order(
                customer=Customer(name="Новый", region="Урал", industry="Энергетика"),
                status=OrderStatus.PAID,
                ordered_at=msk(2026, 10, 5, 10),
                paid_at=msk(2026, 10, 5, 11),
            ),
            product=Product(
                sku="NEW-1", name="Новый насос", category="Насосы", cost=Decimal("1")
            ),
            quantity=1,
            unit_price=Decimal("50000.00"),
        )
    )
    sample.flush()

    live = client.get("/api/analytics/categories", params=OCTOBER_VS_SEPTEMBER).json()
    saved = client.get(f"/api/reports/{report['id']}").json()

    assert live["net_revenue"]["absolute"] == "-241500.00"
    assert saved["result"]["net_revenue"]["absolute"] == "-291500.00"


def test_anomaly_report_and_listing(client: TestClient, sample: Session) -> None:
    """Anomaly reports are saved too; the list shows newest first, no bodies."""
    first = client.post(
        "/api/reports", json={"kind": "comparison", **OCTOBER_VS_SEPTEMBER}
    ).json()
    second = client.post(
        "/api/reports",
        json={"kind": "anomalies", "start": "2026-01-01", "end": "2026-10-01"},
    ).json()

    listing = client.get("/api/reports", params={"limit": 10}).json()

    ids = [item["id"] for item in listing["items"]]
    assert {first["id"], second["id"]} <= set(ids)
    assert all("result" not in item for item in listing["items"])
    assert second["result"]["seed"] == 42
    stored = sample.scalar(select(Report).where(Report.id == uuid.UUID(second["id"])))
    assert stored is not None and stored.app_version


def test_unknown_report_is_404(client: TestClient) -> None:
    """A valid but unknown UUID is 404 with a short message."""
    response = client.get(f"/api/reports/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Report not found"}


def test_read_session_rejects_writes(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real read dependency opens a READ ONLY transaction in PostgreSQL."""
    monkeypatch.setattr(dependencies, "get_engine", lambda: migrated_engine)
    sessions = read_session()
    session = next(sessions)
    try:
        isolation = session.scalar(text("SHOW transaction_isolation"))
        with pytest.raises(DBAPIError) as error:
            session.execute(
                text(
                    "INSERT INTO customers (name, region, industry) "
                    "VALUES ('x', 'y', 'z')"
                )
            )
    finally:
        sessions.close()

    assert isolation == "repeatable read"
    assert isinstance(error.value.orig, errors.ReadOnlySqlTransaction)
