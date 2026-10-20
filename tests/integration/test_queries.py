"""SQL-запросы из папки sql/ дают ответы, посчитанные вручную заранее.

Учебный набор описан в app/db/sample.py вместе с ожидаемыми числами.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import Customer, Order, Refund
from app.db.sample import add_sample_data

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def run_sql(session: Session, name: str) -> list[Any]:
    """Выполнить файл из sql/ так же, как его выполнил бы psql.

    Строки результата — объекты Row: к столбцу можно обратиться по имени
    (row.order_total), а tuple(row) даёт обычный кортеж значений.
    """
    query = (SQL_DIR / name).read_text(encoding="utf-8")
    return list(session.execute(text(query)))


@pytest.fixture
def sample(db_session: Session) -> Session:
    """Сессия с загруженным учебным набором (откатится после теста)."""
    add_sample_data(db_session)
    return db_session


def test_sample_data_counts(sample: Session) -> None:
    """В наборе 2 клиента, 5 заказов и 2 возврата."""
    count = func.count()
    assert sample.scalar(select(count).select_from(Customer)) == 2
    assert sample.scalar(select(count).select_from(Order)) == 5
    assert sample.scalar(select(count).select_from(Refund)) == 2


def test_paid_order_totals(sample: Session) -> None:
    """Только оплаченные заказы; сумма позиций с учётом скидки."""
    rows = run_sql(sample, "01_paid_order_totals.sql")

    assert [(row.items, row.order_total) for row in rows] == [
        (2, Decimal("190000.00")),
        (1, Decimal("120000.00")),
        (1, Decimal("18000.00")),
    ]


def test_net_revenue_by_month(sample: Session) -> None:
    """Возврат уменьшает выручку месяца, в котором он проведён."""
    rows = run_sql(sample, "02_net_revenue_by_month.sql")

    assert [tuple(row) for row in rows] == [
        (
            date(2026, 9, 1),
            Decimal("310000.00"),
            Decimal("1000.00"),
            Decimal("309000.00"),
        ),
        (
            date(2026, 10, 1),
            Decimal("18000.00"),
            Decimal("500.00"),
            Decimal("17500.00"),
        ),
    ]


def test_month_depends_on_time_zone(sample: Session) -> None:
    """Заказ, оплаченный 1 октября в 01:30 МСК, по UTC попал бы в сентябрь."""
    utc_september = sample.scalar(
        text(
            "SELECT SUM(ROUND(oi.quantity * oi.unit_price * (1 - oi.discount), 2)) "
            "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
            "WHERE o.status = 'paid' "
            "AND date_trunc('month', o.paid_at AT TIME ZONE 'UTC') = '2026-09-01'"
        )
    )

    assert utc_september == Decimal("328000.00")  # а по Москве — 310 000.00


def test_sales_by_category(sample: Session) -> None:
    """Категории отсортированы по продажам, доли в сумме дают 100 %."""
    rows = run_sql(sample, "03_sales_by_category.sql")

    assert [tuple(row) for row in rows] == [
        ("Насосы", Decimal("300000.00"), Decimal("91.5")),
        ("Запорная арматура", Decimal("18000.00"), Decimal("5.5")),
        ("Датчики", Decimal("10000.00"), Decimal("3.0")),
    ]


def test_double_counting_pitfall(sample: Session) -> None:
    """JOIN с двумя возвратами удваивает позицию в 10 000 ₽: 338 000 вместо 328 000."""
    (row,) = run_sql(sample, "04_double_counting.sql")

    assert row.naive_sales == Decimal("338000.00")
    assert row.correct_sales == Decimal("328000.00")
    assert row.refunds == Decimal("1500.00")
