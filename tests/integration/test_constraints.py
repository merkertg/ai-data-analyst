"""PostgreSQL сама отвергает некорректные строки: ключи, проверки, уникальность.

Каждый тест вставляет одну плохую строку и проверяет, что база назвала
именно то ограничение, которое должно сработать.
"""

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import NamedTuple

import pytest
from psycopg import errors
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Customer,
    InventorySnapshot,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Refund,
)
from app.db.sample import msk


def violated_constraint(error: DBAPIError) -> str | None:
    """Имя ограничения из диагностики PostgreSQL (psycopg: error.orig.diag)."""
    original = error.orig
    assert isinstance(original, errors.Error)
    return original.diag.constraint_name


class Rows(NamedTuple):
    """Корректные строки, к которым привязываются проверяемые плохие строки."""

    customer: Customer
    product: Product
    order: Order


def base_rows(session: Session) -> Rows:
    """Корректные клиент, товар и оплаченный заказ для построения плохих строк."""
    customer = Customer(name="ООО «Тест»", region="Урал", industry="Энергетика")
    product = Product(
        sku="TST-001", name="Тестовый насос", category="Насосы", cost=Decimal("10")
    )
    order = Order(
        customer=customer,
        status=OrderStatus.PAID,
        ordered_at=msk(2026, 9, 1, 10),
        paid_at=msk(2026, 9, 1, 11),
    )
    session.add_all([customer, product, order])
    session.flush()
    return Rows(customer, product, order)


def item(order: Order, product: Product, **values: object) -> OrderItem:
    """Позиция заказа с корректными значениями по умолчанию."""
    fields: dict[str, object] = {
        "order": order,
        "product": product,
        "quantity": 1,
        "unit_price": Decimal("100.00"),
    }
    fields.update(values)
    return OrderItem(**fields)


# Каждый случай: как построить плохую строку → какое ограничение сработает.
CASES: dict[str, tuple[Callable[[Rows], object], str]] = {
    "blank customer name": (
        lambda rows: Customer(name="  ", region="Юг", industry="Химия"),
        "ck_customers_name_not_blank",
    ),
    "negative product cost": (
        lambda rows: Product(
            sku="X-1", name="X", category="Датчики", cost=Decimal("-1")
        ),
        "ck_products_cost_not_negative",
    ),
    "duplicate sku": (
        lambda rows: Product(
            sku="TST-001", name="Копия", category="Насосы", cost=Decimal("1")
        ),
        "uq_products_sku",
    ),
    "order of unknown customer": (
        lambda rows: Order(customer_id=999_999, ordered_at=msk(2026, 9, 1, 10)),
        "fk_orders_customer_id_customers",
    ),
    "unknown order status": (
        lambda rows: Order(
            customer=rows.customer, status="shipped", ordered_at=msk(2026, 9, 1, 10)
        ),
        "ck_orders_status_allowed",
    ),
    "paid order without paid_at": (
        lambda rows: Order(
            customer=rows.customer,
            status=OrderStatus.PAID,
            ordered_at=msk(2026, 9, 1, 10),
        ),
        "ck_orders_paid_at_matches_status",
    ),
    "pending order with paid_at": (
        lambda rows: Order(
            customer=rows.customer,
            status=OrderStatus.PENDING,
            ordered_at=msk(2026, 9, 1, 10),
            paid_at=msk(2026, 9, 1, 11),
        ),
        "ck_orders_paid_at_matches_status",
    ),
    "paid before ordered": (
        lambda rows: Order(
            customer=rows.customer,
            status=OrderStatus.PAID,
            ordered_at=msk(2026, 9, 2, 10),
            paid_at=msk(2026, 9, 1, 10),
        ),
        "ck_orders_paid_after_ordered",
    ),
    "zero quantity": (
        lambda rows: item(rows.order, rows.product, quantity=0),
        "ck_order_items_quantity_positive",
    ),
    "negative unit price": (
        lambda rows: item(rows.order, rows.product, unit_price=Decimal("-0.01")),
        "ck_order_items_unit_price_not_negative",
    ),
    "discount of 100 percent": (
        lambda rows: item(rows.order, rows.product, discount=Decimal("1")),
        "ck_order_items_discount_range",
    ),
    "zero refund": (
        lambda rows: Refund(
            order_item=item(rows.order, rows.product),
            amount=Decimal("0"),
            processed_at=msk(2026, 9, 2, 10),
        ),
        "ck_refunds_amount_positive",
    ),
    "negative stock": (
        lambda rows: InventorySnapshot(
            product=rows.product, snapshot_date=date(2026, 9, 30), quantity=-1
        ),
        "ck_inventory_snapshots_quantity_not_negative",
    ),
}


@pytest.mark.parametrize("case", CASES, ids=list(CASES))
def test_invalid_row_is_rejected(db_session: Session, case: str) -> None:
    """Плохая строка вызывает IntegrityError с именем нужного ограничения."""
    build, constraint = CASES[case]
    db_session.add(build(base_rows(db_session)))

    with pytest.raises(IntegrityError) as error:
        db_session.flush()

    assert violated_constraint(error.value) == constraint


def test_missing_required_value_is_rejected(db_session: Session) -> None:
    """NOT NULL: клиент без региона не сохраняется (SQLSTATE 23502)."""
    db_session.add(Customer(name="ООО «Без региона»", industry="Химия"))

    with pytest.raises(IntegrityError) as error:
        db_session.flush()

    assert isinstance(error.value.orig, errors.NotNullViolation)


def test_same_product_twice_in_order_is_rejected(db_session: Session) -> None:
    """Один товар — одна строка заказа: дубль нарушает уникальность."""
    _, product, order = base_rows(db_session)
    db_session.add_all([item(order, product), item(order, product, quantity=2)])

    with pytest.raises(IntegrityError) as error:
        db_session.flush()

    assert violated_constraint(error.value) == "uq_order_items_order_id_product_id"


def test_second_snapshot_for_same_day_is_rejected(db_session: Session) -> None:
    """Один снимок остатка товара на одну дату."""
    _, product, _ = base_rows(db_session)
    day = date(2026, 9, 30)
    db_session.add_all(
        [
            InventorySnapshot(product=product, snapshot_date=day, quantity=5),
            InventorySnapshot(product=product, snapshot_date=day, quantity=7),
        ]
    )

    with pytest.raises(IntegrityError) as error:
        db_session.flush()

    assert (
        violated_constraint(error.value)
        == "uq_inventory_snapshots_product_id_snapshot_date"
    )


def test_sold_product_cannot_be_deleted(db_session: Session) -> None:
    """RESTRICT: товар из заказа нельзя удалить — пропала бы история продаж."""
    _, product, order = base_rows(db_session)
    db_session.add(item(order, product))
    db_session.flush()

    with pytest.raises(IntegrityError) as error:
        db_session.execute(delete(Product).where(Product.id == product.id))

    assert violated_constraint(error.value) == "fk_order_items_product_id_products"


def test_customer_with_orders_cannot_be_deleted(db_session: Session) -> None:
    """RESTRICT: клиента с заказами удалить нельзя."""
    customer, _, _ = base_rows(db_session)

    with pytest.raises(IntegrityError) as error:
        db_session.execute(delete(Customer).where(Customer.id == customer.id))

    assert violated_constraint(error.value) == "fk_orders_customer_id_customers"


def test_deleting_order_removes_its_items(db_session: Session) -> None:
    """CASCADE: позиции удаляются вместе с заказом на стороне базы."""
    _, product, order = base_rows(db_session)
    db_session.add(item(order, product))
    db_session.flush()
    order_id = order.id
    db_session.expunge_all()

    db_session.execute(delete(Order).where(Order.id == order_id))

    remaining = db_session.scalars(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()
    assert remaining == []


def test_order_with_refund_cannot_be_deleted(db_session: Session) -> None:
    """Каскад упирается в возврат: проведённые деньги удалить нельзя."""
    _, product, order = base_rows(db_session)
    line = item(order, product)
    db_session.add(
        Refund(
            order_item=line, amount=Decimal("10.00"), processed_at=msk(2026, 9, 3, 9)
        )
    )
    db_session.flush()
    order_id = order.id
    db_session.expunge_all()

    with pytest.raises(IntegrityError) as error:
        db_session.execute(delete(Order).where(Order.id == order_id))

    assert violated_constraint(error.value) == "fk_refunds_order_item_id_order_items"


def test_money_round_trip_is_exact(db_session: Session) -> None:
    """NUMERIC возвращает ровно то, что записали, — тип Decimal, а не float."""
    _, product, order = base_rows(db_session)
    line = item(order, product, unit_price=Decimal("0.10"), discount=Decimal("0.3333"))
    db_session.add(line)
    db_session.flush()
    db_session.expire_all()

    stored = db_session.get(OrderItem, line.id)

    assert stored is not None
    assert stored.unit_price == Decimal("0.10")
    assert isinstance(stored.unit_price, Decimal)
    assert stored.discount == Decimal("0.3333")


def test_money_overflow_is_rejected(db_session: Session) -> None:
    """NUMERIC(12, 2) не примет 10 миллиардов: лучше ошибка, чем искажение."""
    db_session.add(
        Product(sku="BIG-1", name="X", category="Насосы", cost=Decimal("1e10"))
    )

    with pytest.raises(DBAPIError) as error:
        db_session.flush()

    assert isinstance(error.value.orig, errors.NumericValueOutOfRange)


def test_timestamps_keep_the_moment(db_session: Session) -> None:
    """timestamptz хранит момент: 01:30 по Москве = 22:30 UTC прошлого дня."""
    _, _, order = base_rows(db_session)
    order.paid_at = msk(2026, 10, 1, 1, 30)
    order.ordered_at = msk(2026, 9, 30, 20)
    db_session.flush()
    db_session.expire_all()

    stored = db_session.get(Order, order.id)

    assert stored is not None and stored.paid_at is not None
    assert stored.paid_at == datetime.fromisoformat("2026-09-30T22:30:00+00:00")
