"""Маленький учебный набор данных с заранее посчитанными ответами.

Он нужен, чтобы вручную попробовать SQL-запросы из папки sql/ и чтобы тесты
сверяли их результаты с числами, посчитанными на бумаге. Большой
демонстрационный датасет появится на этапе 03.

Загрузка в базу разработки (только если таблицы пусты):

    uv run python -m app.db.sample
"""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
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
from app.db.session import get_engine

# Отчётные периоды компании считаются по московскому времени.
MOSCOW = ZoneInfo("Europe/Moscow")


def msk(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Момент времени по Москве; в базе он хранится как timestamptz."""
    return datetime(year, month, day, hour, minute, tzinfo=MOSCOW)


def add_sample_data(session: Session) -> None:
    """Добавить в сессию 2 клиента, 3 товара, 5 заказов и 2 возврата.

    Ожидаемые ответы (в рублях, без НДС):
    - оплаченные заказы: №1 = 190 000.00, №2 = 120 000.00, №5 = 18 000.00;
    - сентябрь: продажи 310 000.00, возвраты 1 000.00, чистая выручка 309 000.00;
    - октябрь: продажи 18 000.00, возвраты 500.00, чистая выручка 17 500.00;
    - заказ №5 оплачен 1 октября в 01:30 по Москве — это ещё 30 сентября
      по UTC: группировка без часового пояса отнесла бы его к сентябрю.

    Функция не вызывает commit: решение о сохранении принимает вызывающий код.
    """
    north = Customer(
        name="ООО «ТехМонтаж-Север»", region="Северо-Запад", industry="Металлургия"
    )
    south = Customer(name="АО «Южный химкомбинат»", region="Юг", industry="Химия")
    pump = Product(
        sku="PMP-100",
        name="Центробежный насос ЦН-100",
        category="Насосы",
        cost=Decimal("70000.00"),
    )
    sensor = Product(
        sku="SNS-020",
        name="Датчик давления ДД-20",
        category="Датчики",
        cost=Decimal("1200.00"),
    )
    valve = Product(
        sku="VLV-050",
        name="Шаровой кран DN50",
        category="Запорная арматура",
        cost=Decimal("3000.00"),
    )
    session.add_all([north, south, pump, sensor, valve])
    session.flush()

    def save(order: Order) -> Order:
        """Сохранить заказ сразу: в пустой базе номера пойдут по порядку 1–5.

        Если добавить все заказы разом, SQLAlchemy сама выберет порядок
        вставки, и номера в выводе SQL-запросов перемешаются.
        """
        session.add(order)
        session.flush()
        return order

    # №1: два насоса со скидкой 10 % и пять датчиков: 180 000 + 10 000.
    sensor_line = OrderItem(product=sensor, quantity=5, unit_price=Decimal("2000.00"))
    save(
        Order(
            customer=north,
            status=OrderStatus.PAID,
            ordered_at=msk(2026, 9, 3, 10),
            paid_at=msk(2026, 9, 5, 12),
            items=[
                OrderItem(
                    product=pump,
                    quantity=2,
                    unit_price=Decimal("100000.00"),
                    discount=Decimal("0.1000"),
                ),
                sensor_line,
            ],
        )
    )
    # №2: один насос без скидки.
    save(
        Order(
            customer=south,
            status=OrderStatus.PAID,
            ordered_at=msk(2026, 9, 18, 15),
            paid_at=msk(2026, 9, 20, 9, 30),
            items=[
                OrderItem(product=pump, quantity=1, unit_price=Decimal("120000.00"))
            ],
        )
    )
    # №3: отменён, №4: не оплачен — в выручку не входят.
    save(
        Order(
            customer=south,
            status=OrderStatus.CANCELLED,
            ordered_at=msk(2026, 9, 25, 11),
            items=[
                OrderItem(product=valve, quantity=10, unit_price=Decimal("4500.00"))
            ],
        )
    )
    save(
        Order(
            customer=north,
            status=OrderStatus.PENDING,
            ordered_at=msk(2026, 9, 29, 16),
            items=[
                OrderItem(product=sensor, quantity=3, unit_price=Decimal("2000.00"))
            ],
        )
    )
    # №5: оплачен в первые минуты октября по Москве.
    save(
        Order(
            customer=north,
            status=OrderStatus.PAID,
            ordered_at=msk(2026, 9, 30, 20),
            paid_at=msk(2026, 10, 1, 1, 30),
            items=[OrderItem(product=valve, quantity=4, unit_price=Decimal("4500.00"))],
        )
    )

    # Два возврата по датчикам из заказа №1: в сентябре и в октябре.
    session.add_all(
        [
            Refund(
                order_item=sensor_line,
                amount=Decimal("1000.00"),
                processed_at=msk(2026, 9, 10, 11),
            ),
            Refund(
                order_item=sensor_line,
                amount=Decimal("500.00"),
                processed_at=msk(2026, 10, 2, 15),
            ),
            InventorySnapshot(
                product=pump, snapshot_date=date(2026, 9, 30), quantity=4
            ),
            InventorySnapshot(
                product=sensor, snapshot_date=date(2026, 9, 30), quantity=120
            ),
            InventorySnapshot(
                product=valve, snapshot_date=date(2026, 9, 30), quantity=0
            ),
        ]
    )
    session.flush()


def main() -> None:
    """Загрузить набор в базу из DATABASE_URL, если там ещё нет клиентов."""
    with Session(get_engine()) as session:
        if session.scalar(select(func.count()).select_from(Customer)):
            print("В базе уже есть клиенты: учебный набор не загружен.")
            return
        add_sample_data(session)
        session.commit()
        print("Учебный набор загружен: 2 клиента, 3 товара, 5 заказов, 2 возврата.")


if __name__ == "__main__":
    main()
