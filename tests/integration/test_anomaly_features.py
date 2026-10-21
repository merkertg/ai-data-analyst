"""Anomaly features match independent calculations on isolated PostgreSQL."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.analytics.anomaly_features import read_features
from app.analytics.anomaly_models import MonthlyPoint
from app.analytics.models import Period
from app.db.models import (
    Customer,
    InventorySnapshot,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Refund,
)
from app.db.sample import add_sample_data, msk

SEPTEMBER = Period.month(2026, 9)
OCTOBER = Period.month(2026, 10)


@pytest.fixture
def sample(db_session: Session) -> Session:
    """Use the documented sample inside the test fixture's rollback boundary."""
    add_sample_data(db_session)
    return db_session


def add_line(
    session: Session,
    sku: str,
    *,
    at: datetime | None = None,
    category: str = "Sensors",
    region: str = "North",
    price: str = "100.00",
    quantity: int = 1,
    discount: str = "0",
    status: OrderStatus = OrderStatus.PAID,
) -> OrderItem:
    """Persist one independent order using exact input money and payment time."""
    moment = at or msk(2026, 9, 15, 12)
    item = OrderItem(
        order=Order(
            customer=Customer(name=sku, region=region, industry="Industry"),
            status=status,
            ordered_at=moment - timedelta(hours=1),
            paid_at=moment if status == OrderStatus.PAID else None,
        ),
        product=Product(sku=sku, name=sku, category=category, cost=Decimal("0.00")),
        quantity=quantity,
        unit_price=Decimal(price),
        discount=Decimal(discount),
    )
    session.add(item)
    session.flush()
    return item


def add_refund(
    session: Session, item: OrderItem, amount: str, *, at: datetime | None = None
) -> None:
    """Persist a partial refund independently of its original payment month."""
    session.add(
        Refund(
            order_item=item,
            amount=Decimal(amount),
            processed_at=at or msk(2026, 9, 20, 12),
        )
    )
    session.flush()


def monthly_index(
    points: list[MonthlyPoint],
) -> dict[tuple[Period, str, str | None], MonthlyPoint]:
    """Index rows without depending on SQL collation or output ordering."""
    result = {(point.period, point.category, point.region): point for point in points}
    assert len(result) == len(points), "A monthly feature group must appear once."
    return result


def test_sample_monthly_features_match_hand_calculated_totals(sample: Session) -> None:
    """Category aggregates and regional slices retain their own exact values."""
    features = read_features(sample, Period(date(2026, 9, 1), date(2026, 11, 1)))
    rows = monthly_index(features.monthly)

    assert len(rows) == 9
    pumps = rows[(SEPTEMBER, "Насосы", None)]
    assert (
        pumps.paid_quantity,
        pumps.paid_sales,
        pumps.discount_rate,
        pumps.refund_rate,
        pumps.paid_lines,
    ) == (Decimal("3"), Decimal("300000.00"), Decimal("0.0625"), Decimal("0"), 2)
    north = rows[(SEPTEMBER, "Насосы", "Северо-Запад")]
    south = rows[(SEPTEMBER, "Насосы", "Юг")]
    assert (north.paid_quantity, north.paid_sales, north.discount_rate) == (
        Decimal("2"),
        Decimal("180000.00"),
        Decimal("0.1"),
    )
    assert (south.paid_quantity, south.paid_sales, south.discount_rate) == (
        Decimal("1"),
        Decimal("120000.00"),
        Decimal("0"),
    )
    sensors = rows[(SEPTEMBER, "Датчики", None)]
    assert (
        sensors.paid_quantity,
        sensors.paid_sales,
        sensors.discount_rate,
        sensors.refund_rate,
        sensors.paid_lines,
    ) == (Decimal("5"), Decimal("10000.00"), Decimal("0"), Decimal("0.1"), 1)
    assert all(isinstance(point.paid_quantity, Decimal) for point in features.monthly)
    assert all(isinstance(point.paid_sales, Decimal) for point in features.monthly)


def test_refund_only_month_keeps_category_and_regional_groups(sample: Session) -> None:
    """A refund creates a later group even without a payment in that month."""
    rows = monthly_index(read_features(sample, OCTOBER).monthly)

    assert set(rows) == {
        (OCTOBER, "Датчики", None),
        (OCTOBER, "Датчики", "Северо-Запад"),
        (OCTOBER, "Запорная арматура", None),
        (OCTOBER, "Запорная арматура", "Северо-Запад"),
    }
    for region in (None, "Северо-Запад"):
        sensors = rows[(OCTOBER, "Датчики", region)]
        assert sensors.paid_quantity == Decimal("0")
        assert sensors.paid_sales == Decimal("0.00")
        assert sensors.discount_rate is None
        assert sensors.refund_rate is None
        assert sensors.paid_lines == 0


def test_sample_lines_and_stock_are_not_multiplied_by_feature_slices(
    sample: Session,
) -> None:
    """Raw paid lines and stock snapshots occur once despite aggregate slices."""
    features = read_features(sample, Period(date(2026, 9, 1), date(2026, 11, 1)))

    assert len(features.lines) == len({point.item_id for point in features.lines}) == 4
    assert sorted(
        (point.category, point.paid_on, point.quantity) for point in features.lines
    ) == [
        ("Датчики", date(2026, 9, 5), 5),
        ("Запорная арматура", date(2026, 10, 1), 4),
        ("Насосы", date(2026, 9, 5), 2),
        ("Насосы", date(2026, 9, 20), 1),
    ]
    assert len(features.stock) == 3
    assert {point.snapshot_date for point in features.stock} == {date(2026, 9, 30)}
    assert sorted(point.quantity for point in features.stock) == [0, 4, 120]
    assert len({point.product_id for point in features.stock}) == 3


def test_multiple_partial_refunds_do_not_inflate_sales_or_quantities(
    db_session: Session,
) -> None:
    """Two refund rows affect the ratio once each without multiplying a sale."""
    item = add_line(db_session, "PARTIAL")
    add_refund(db_session, item, "10.00")
    add_refund(db_session, item, "20.00")

    features = read_features(db_session, SEPTEMBER)
    rows = monthly_index(features.monthly)

    assert len(features.lines) == 1
    for region in (None, "North"):
        point = rows[(SEPTEMBER, "Sensors", region)]
        assert point.paid_quantity == Decimal("1")
        assert point.paid_sales == Decimal("100.00")
        assert point.paid_lines == 1
        assert point.refund_rate == Decimal("0.3")


def test_discount_rate_is_weighted_by_gross_amount(db_session: Session) -> None:
    """Different line sizes use an amount-weighted rate, not an average of rates."""
    add_line(db_session, "WEIGHT-SMALL", price="100.00", discount="0.5000")
    add_line(
        db_session,
        "WEIGHT-LARGE",
        price="100.00",
        quantity=3,
        discount="0.1000",
        region="South",
    )

    rows = monthly_index(read_features(db_session, SEPTEMBER).monthly)

    point = rows[(SEPTEMBER, "Sensors", None)]
    assert point.paid_quantity == Decimal("4")
    assert point.paid_sales == Decimal("320.00")
    assert point.discount_rate == Decimal("0.2")
    assert point.paid_lines == 2
    assert rows[(SEPTEMBER, "Sensors", "North")].discount_rate == Decimal("0.5")
    assert rows[(SEPTEMBER, "Sensors", "South")].discount_rate == Decimal("0.1")


def test_money_is_rounded_per_line_before_monthly_aggregation(
    db_session: Session,
) -> None:
    """Two 0.045 RUB discounted lines become 0.10 RUB, not an aggregate 0.09."""
    add_line(db_session, "ROUND-A", price="0.05", discount="0.1000")
    add_line(db_session, "ROUND-B", price="0.05", discount="0.1000")

    rows = monthly_index(read_features(db_session, SEPTEMBER).monthly)

    for region in (None, "North"):
        point = rows[(SEPTEMBER, "Sensors", region)]
        assert point.paid_sales == Decimal("0.10")
        assert point.paid_quantity == Decimal("2")
        assert point.paid_lines == 2
        assert point.discount_rate == Decimal("0")


def test_payment_and_refund_boundaries_use_moscow_in_any_session_timezone(
    db_session: Session,
) -> None:
    """UTC event inputs are bucketed by Moscow dates at half-open boundaries."""
    db_session.execute(text("SET LOCAL TIME ZONE 'Pacific/Honolulu'"))
    start = msk(2026, 9, 1, 0).astimezone(UTC)
    end = msk(2026, 10, 1, 0).astimezone(UTC)
    moments = [
        start - timedelta(microseconds=1),
        start,
        end - timedelta(microseconds=1),
        end,
    ]
    for index, moment in enumerate(moments):
        add_line(db_session, f"BOUNDARY-{index}", at=moment)
    older = add_line(db_session, "OLDER-REFUND", at=msk(2026, 8, 1, 12))
    for moment in moments:
        add_refund(db_session, older, "1.00", at=moment)

    features = read_features(db_session, SEPTEMBER)
    rows = monthly_index(features.monthly)

    assert sorted(point.paid_on for point in features.lines) == [
        date(2026, 9, 1),
        date(2026, 9, 30),
    ]
    for region in (None, "North"):
        point = rows[(SEPTEMBER, "Sensors", region)]
        assert point.paid_sales == Decimal("200.00")
        assert point.paid_quantity == Decimal("2")
        assert point.paid_lines == 2
        assert point.refund_rate == Decimal("0.01")


def test_partial_calendar_months_are_clipped_without_empty_global_groups(
    db_session: Session,
) -> None:
    """Only events inside the requested sub-month dates contribute to each slice."""
    for month, day in [(9, 10), (9, 20), (10, 10), (10, 20)]:
        add_line(db_session, f"CLIPPED-{month}-{day}", at=msk(2026, month, day, 12))
    period = Period(date(2026, 9, 15), date(2026, 10, 15))

    features = read_features(db_session, period)
    rows = monthly_index(features.monthly)

    assert {point.period for point in features.monthly} == {
        Period(date(2026, 9, 15), date(2026, 10, 1)),
        Period(date(2026, 10, 1), date(2026, 10, 15)),
    }
    assert len(rows) == 4
    assert all(point.paid_sales == Decimal("100.00") for point in features.monthly)
    assert sorted(point.paid_on for point in features.lines) == [
        date(2026, 9, 20),
        date(2026, 10, 10),
    ]


def test_missing_months_do_not_invent_category_groups(sample: Session) -> None:
    """Months without payments or refunds stay absent from sparse group features."""
    period = Period(date(2026, 8, 15), date(2026, 11, 10))

    features = read_features(sample, period)

    assert {point.period for point in features.monthly} == {SEPTEMBER, OCTOBER}
    assert len(features.monthly) == 9


def test_zero_value_sales_keep_undefined_ratios(db_session: Session) -> None:
    """A free paid line has quantity and line count but neither ratio denominator."""
    add_line(db_session, "FREE", price="0.00", quantity=2)

    features = read_features(db_session, SEPTEMBER)

    assert len(features.monthly) == 2
    assert len(features.lines) == 1
    for point in features.monthly:
        assert point.paid_quantity == Decimal("2")
        assert point.paid_sales == Decimal("0.00")
        assert point.paid_lines == 1
        assert point.discount_rate is None
        assert point.refund_rate is None


@pytest.mark.parametrize("status", [OrderStatus.PENDING, OrderStatus.CANCELLED])
def test_unpaid_lines_and_their_refunds_are_excluded(
    db_session: Session, status: OrderStatus
) -> None:
    """An invalid refund attached to an unpaid order cannot enter any feature."""
    item = add_line(db_session, "UNPAID", status=status)
    add_refund(db_session, item, "10.00")

    features = read_features(db_session, SEPTEMBER)

    assert features.monthly == []
    assert features.lines == []
    assert features.stock == []


def test_stock_date_bounds_are_half_open_and_independent_of_sales(
    db_session: Session,
) -> None:
    """Inventory-only data remains visible exactly on inclusive/exclusive dates."""
    product = Product(sku="STOCK", name="Stock", category="Sensors", cost=Decimal("0"))
    for snapshot_date, quantity in [
        (date(2026, 8, 31), 1),
        (date(2026, 9, 1), 2),
        (date(2026, 9, 30), 3),
        (date(2026, 10, 1), 4),
    ]:
        db_session.add(
            InventorySnapshot(
                product=product, snapshot_date=snapshot_date, quantity=quantity
            )
        )
    db_session.flush()

    features = read_features(db_session, SEPTEMBER)

    assert features.monthly == []
    assert features.lines == []
    assert sorted(
        (point.snapshot_date, point.quantity) for point in features.stock
    ) == [(date(2026, 9, 1), 2), (date(2026, 9, 30), 3)]
    assert {point.product_id for point in features.stock} == {product.id}


def test_empty_database_has_no_invented_features(db_session: Session) -> None:
    """No records produce empty lists rather than aggregate zero observations."""
    features = read_features(db_session, SEPTEMBER)

    assert features.monthly == []
    assert features.lines == []
    assert features.stock == []


def test_feature_reader_does_not_autoflush_or_commit(sample: Session) -> None:
    """Reading preserves invalid pending objects and the caller's rollback choice."""
    invalid = Customer(name="", region="North", industry="Industry")
    sample.add(invalid)

    features = read_features(sample, SEPTEMBER)

    assert len(features.monthly) == 5
    assert len(features.lines) == 3
    assert len(features.stock) == 3
    assert invalid in sample.new
    assert invalid.id is None
    sample.expunge(invalid)
    sample.rollback()

    assert sample.scalar(select(func.count()).select_from(Order)) == 0
