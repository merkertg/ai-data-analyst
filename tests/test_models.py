"""Структура моделей без базы: таблицы, денежные типы и правила удаления."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric

from app.db.base import Base
from app.db.models import OrderStatus

# Импорт моделей регистрирует их таблицы в Base.metadata.
TABLES = Base.metadata.tables


def test_six_tables_are_registered() -> None:
    """Схема этапа 02 состоит ровно из шести таблиц предметной области."""
    assert set(TABLES) == {
        "customers",
        "products",
        "orders",
        "order_items",
        "refunds",
        "inventory_snapshots",
    }


def test_money_columns_are_exact_numeric() -> None:
    """Деньги хранятся как NUMERIC(12, 2), а в Python читаются как Decimal."""
    money_columns = [
        TABLES["products"].c.cost,
        TABLES["order_items"].c.unit_price,
        TABLES["refunds"].c.amount,
    ]
    for column in money_columns:
        assert isinstance(column.type, Numeric)
        assert (column.type.precision, column.type.scale) == (12, 2)
        assert column.type.asdecimal


def test_delete_rules() -> None:
    """Позиции удаляются вместе с заказом; остальные связи защищают историю."""
    rules = {
        (table.name, constraint.referred_table.name): constraint.ondelete
        for table in TABLES.values()
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    assert rules == {
        ("orders", "customers"): "RESTRICT",
        ("order_items", "orders"): "CASCADE",
        ("order_items", "products"): "RESTRICT",
        ("refunds", "order_items"): "RESTRICT",
        ("inventory_snapshots", "products"): "RESTRICT",
    }


def test_every_constraint_and_index_has_a_name() -> None:
    """Соглашение об именах даёт имя каждому ограничению и индексу."""
    for table in TABLES.values():
        for constraint in table.constraints:
            assert constraint.name, f"Безымянное ограничение в {table.name}"
        for index in table.indexes:
            assert index.name, f"Безымянный индекс в {table.name}"


def test_order_status_values_match_check_constraint() -> None:
    """Значения OrderStatus совпадают с правилом CHECK в таблице orders."""
    check = next(
        constraint
        for constraint in TABLES["orders"].constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_orders_status_allowed"
    )

    for status in OrderStatus:
        assert f"'{status.value}'" in str(check.sqltext)
