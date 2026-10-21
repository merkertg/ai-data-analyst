"""Таблицы корпоративной базы IndustrialFlow: клиенты, товары, заказы, возвраты.

Правила целостности записаны в самой PostgreSQL (CHECK, FOREIGN KEY, UNIQUE):
некорректную строку отвергнет база, даже если её вставит не наше приложение.
Денежные суммы — NUMERIC и Decimal, никогда не float.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# NUMERIC(12, 2): до 9 999 999 999.99 ₽ с точностью до копейки.
Money = Numeric(12, 2)
# Скидка — доля от 0 до 1 с четырьмя знаками: 0.1250 = 12.5 %.
DiscountRate = Numeric(5, 4)


class OrderStatus(StrEnum):
    """Состояние заказа. В выручку попадают только оплаченные заказы."""

    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class Customer(Base):
    """Клиент — промышленное предприятие в одном из регионов продаж."""

    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(trim(region)) > 0", name="region_not_blank"),
        CheckConstraint("length(trim(industry)) > 0", name="industry_not_blank"),
        Index(None, "region"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    region: Mapped[str] = mapped_column(String(50))
    industry: Mapped[str] = mapped_column(String(80))

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(Base):
    """Товар каталога: насос, компрессор, арматура, датчик и т. п."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("length(trim(sku)) > 0", name="sku_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("cost >= 0", name="cost_not_negative"),
        Index(None, "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Артикул уникален: по нему товар узнают в выгрузках и отчётах.
    sku: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    # Себестоимость единицы; цена продажи хранится в позиции заказа.
    cost: Mapped[Decimal] = mapped_column(Money)


class Order(Base):
    """Заказ клиента. Оплата фиксируется временем paid_at."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled')", name="status_allowed"
        ),
        # Оплаченный заказ обязан иметь время оплаты, остальные — не иметь.
        CheckConstraint(
            "(status = 'paid') = (paid_at IS NOT NULL)", name="paid_at_matches_status"
        ),
        CheckConstraint("paid_at >= ordered_at", name="paid_after_ordered"),
        Index(None, "customer_id"),
        # Выручка считается по дате оплаты: индекс ускорит отбор периода.
        Index(None, "paid_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # RESTRICT: клиента с заказами удалить нельзя — история продаж важнее.
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(
        String(16), default=OrderStatus.PENDING, server_default=OrderStatus.PENDING
    )
    # timestamptz: момент времени без двусмысленности часовых поясов.
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )


class OrderItem(Base):
    """Позиция заказа: какой товар, сколько, по какой цене и со скидкой."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_not_negative"),
        CheckConstraint("discount >= 0 AND discount < 1", name="discount_range"),
        # Один товар — одна строка заказа: количество складывается в quantity.
        UniqueConstraint("order_id", "product_id"),
        Index(None, "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # CASCADE: позиции не существуют без заказа и удаляются вместе с ним.
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    # RESTRICT: проданный товар нельзя удалить из каталога.
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT")
    )
    quantity: Mapped[int] = mapped_column(Integer)
    # Цена за единицу на момент продажи, без НДС.
    unit_price: Mapped[Decimal] = mapped_column(Money)
    discount: Mapped[Decimal] = mapped_column(
        DiscountRate, default=Decimal("0"), server_default="0"
    )

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
    refunds: Mapped[list["Refund"]] = relationship(back_populates="order_item")


class Refund(Base):
    """Возврат денег по позиции; уменьшает выручку в месяце проведения."""

    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index(None, "order_item_id"),
        Index(None, "processed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # RESTRICT: позицию с проведённым возвратом удалить нельзя.
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    amount: Mapped[Decimal] = mapped_column(Money)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    order_item: Mapped[OrderItem] = relationship(back_populates="refunds")


class InventorySnapshot(Base):
    """Остаток товара на складе на конец дня."""

    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_not_negative"),
        # Один снимок товара на одну дату.
        UniqueConstraint("product_id", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT")
    )
    snapshot_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)

    product: Mapped[Product] = relationship()


class ReportKind(StrEnum):
    """Вид сохранённого отчёта: сравнение периодов или поиск аномалий."""

    COMPARISON = "comparison"
    ANOMALIES = "anomalies"


class Report(Base):
    """Сохранённый аналитический отчёт: параметры запроса и точный результат.

    Отчёт — снимок: результат записан один раз и потом не пересчитывается,
    даже если данные изменятся. Поэтому вместе с ним хранятся параметры
    и версия кода, которыми его можно воспроизвести.
    """

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("kind IN ('comparison', 'anomalies')", name="kind_allowed"),
        # Список отчётов показывается от новых к старым.
        Index(None, "created_at"),
    )

    # UUID, а не 1, 2, 3: номер отчёта нельзя угадать перебором.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32))
    # JSONB: параметры и результат хранятся как JSON; деньги в нём — строки.
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    app_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
