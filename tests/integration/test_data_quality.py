"""Cross-row business rules on the isolated PostgreSQL test database."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.quality import QualityReport, check_quality
from app.db.models import Customer, Order, OrderItem, OrderStatus, Product, Refund
from app.db.sample import add_sample_data, msk


def violation_counts(report: QualityReport) -> dict[str, int]:
    """Use check names so tests explain which business rule rejects each dataset."""
    return {check.name: check.violations for check in report.checks}


def line(
    session: Session,
    *,
    status: OrderStatus = OrderStatus.PAID,
    unit_price: str = "100.00",
    discount: str = "0",
    quantity: int = 1,
) -> OrderItem:
    """Persist one independent order line with exact monetary test values."""
    count = session.scalar(select(func.count()).select_from(Product)) or 0
    product = Product(
        sku=f"QUALITY-{count + 1}",
        name="Quality test product",
        category="Sensors",
        cost=Decimal("1.00"),
    )
    customer = Customer(name="Quality customer", region="North", industry="Industry")
    order = Order(
        customer=customer,
        status=status,
        ordered_at=msk(2026, 9, 1, 10),
        paid_at=msk(2026, 9, 1, 11) if status == OrderStatus.PAID else None,
    )
    result = OrderItem(
        order=order,
        product=product,
        quantity=quantity,
        unit_price=Decimal(unit_price),
        discount=Decimal(discount),
    )
    session.add(result)
    session.flush()
    return result


def refund(session: Session, item: OrderItem, amount: str, *, hour: int = 12) -> None:
    """Persist a refund without bypassing the existing PostgreSQL constraints."""
    session.add(
        Refund(
            order_item=item,
            amount=Decimal(amount),
            processed_at=msk(2026, 9, 1, hour),
        )
    )
    session.flush()


def test_empty_database_has_no_business_violations(db_session: Session) -> None:
    """An empty dataset is valid; empty_orders means orders without their lines."""
    report = check_quality(db_session)

    assert report.passed
    assert violation_counts(report) == {
        "empty_orders": 0,
        "excessive_refunds": 0,
        "refunds_on_unpaid_orders": 0,
        "refunds_before_payment": 0,
    }


def test_sample_dataset_passes_quality(db_session: Session) -> None:
    """Existing sample data remains compatible with the new cross-row rules."""
    add_sample_data(db_session)

    assert check_quality(db_session).passed


def test_order_without_lines_is_reported(db_session: Session) -> None:
    """A SQL-valid order without a line is unusable for sales analytics."""
    db_session.add(
        Order(
            customer=Customer(name="Empty", region="North", industry="Industry"),
            status=OrderStatus.PENDING,
            ordered_at=msk(2026, 9, 1, 10),
        )
    )
    db_session.flush()

    assert violation_counts(check_quality(db_session))["empty_orders"] == 1


def test_partial_refunds_are_summed_per_line(db_session: Session) -> None:
    """Individually valid partial refunds cannot collectively exceed the line."""
    first = line(db_session, quantity=2, unit_price="100.00", discount="0.1000")
    second = line(db_session)
    refund(db_session, first, "100.00")
    refund(db_session, first, "80.01")
    refund(db_session, second, "100.00")

    counts = violation_counts(check_quality(db_session))

    assert counts["excessive_refunds"] == 1
    assert sum(counts.values()) == 1


@pytest.mark.parametrize("refund_amount, violations", [("0.05", 0), ("0.06", 1)])
def test_discounted_line_is_rounded_before_refund_comparison(
    db_session: Session, refund_amount: str, violations: int
) -> None:
    """PostgreSQL rounds 0.05 * (1 - 0.1) = 0.045 to exactly 0.05 RUB."""
    item = line(db_session, unit_price="0.05", discount="0.1000")
    refund(db_session, item, refund_amount)

    assert (
        violation_counts(check_quality(db_session))["excessive_refunds"] == violations
    )


@pytest.mark.parametrize("status", [OrderStatus.PENDING, OrderStatus.CANCELLED])
def test_refunds_require_paid_orders(db_session: Session, status: OrderStatus) -> None:
    """Foreign keys permit these rows; the quality report catches their status."""
    item = line(db_session, status=status)
    refund(db_session, item, "10.00")
    refund(db_session, item, "20.00")

    counts = violation_counts(check_quality(db_session))

    assert counts["refunds_on_unpaid_orders"] == 2
    assert counts["refunds_before_payment"] == 0
    assert sum(counts.values()) == 2


@pytest.mark.parametrize("hour, violations", [(10, 1), (11, 0), (12, 0)])
def test_refund_timing_uses_payment_instant(
    db_session: Session, hour: int, violations: int
) -> None:
    """A refund before payment fails; the same instant and later are allowed."""
    item = line(db_session)
    refund(db_session, item, "10.00", hour=hour)

    assert (
        violation_counts(check_quality(db_session))["refunds_before_payment"]
        == violations
    )


def test_quality_checks_do_not_flush_or_mutate_session(db_session: Session) -> None:
    """A pending invalid row stays pending while the persisted dataset is read."""
    item = line(db_session)
    refund(db_session, item, "10.00")
    invalid = Customer(name="", region="North", industry="Industry")
    db_session.add(invalid)

    first = check_quality(db_session)
    second = check_quality(db_session)

    assert first == second
    assert first.passed
    assert invalid in db_session.new
    assert invalid.id is None
    db_session.expunge(invalid)
    assert db_session.scalar(select(func.count()).select_from(Refund)) == 1
    assert db_session.scalar(select(func.count()).select_from(OrderItem)) == 1
