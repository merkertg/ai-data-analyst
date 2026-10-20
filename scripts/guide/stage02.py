"""Разделы 12–20: этап 02 — PostgreSQL, таблицы, правила, миграции, SQL, тесты."""

from reportlab.platypus import KeepTogether, Spacer

from guide.diagrams import (
    compose_services,
    double_count,
    er_diagram,
    integration_fixtures,
    migration_flow,
    ready_flow,
    timezone_timeline,
)
from guide.i18n import tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BLUE,
    BLUE_L,
    CELL,
    GREEN,
    GREEN_L,
    H2,
    ORANGE,
    ORANGE_L,
    SMALL,
    TEAL,
    TEAL_L,
    VIOLET,
    VIOLET_L,
    Diagram,
    W,
    callout,
    cards,
    code_block,
    mono,
    p,
    simple_table,
)
from guide.sources import (
    ALEMBIC_OUTPUT,
    PSQL_CATEGORIES,
    PSQL_DOUBLE_COUNT,
    PSQL_ERRORS,
    PSQL_NET_REVENUE,
    PSQL_ORDER_TOTALS,
    READY_OUTPUT,
    class_source,
    function_source,
    read_source,
    without_comments,
)
from guide.toc import section


def sql_body(name: str) -> str:
    """Текст SQL-файла без вводных строк комментария: их пересказывает PDF."""
    lines = read_source(f"sql/{name}").splitlines()
    first = next(i for i, line in enumerate(lines) if not line.startswith("--"))
    return "\n".join(lines[first:])


def add_stage02(story, verification, counts):
    """Добавить в story разделы 12–20 об этапе 02."""
    tests = verification["tests"]

    # 12. PostgreSQL в Docker
    section(
        story,
        12,
        tr(
            "Где живёт база, как к ней подключаются приложение и тесты и что "
            "переживает перезапуск.",
            "Where the database lives, how the app and tests connect to it and what "
            "survives a restart.",
        ),
        TEAL,
    )
    story += [
        Diagram(160, compose_services),
        Spacer(1, 10),
        code_block(
            "cp .env.example .env\n"
            "docker compose up --detach --wait db\n"
            "uv run alembic upgrade head\n"
            "uv run python -m app.db.sample\n"
            "docker compose exec db psql -U analyst -d industrialflow\n"
            "docker compose stop"
        ),
        Spacer(1, 8),
        simple_table(
            [tr("Решение", "Decision"), tr("Зачем", "Why")],
            [
                [
                    tr("Порт только на 127.0.0.1", "Port bound to 127.0.0.1 only"),
                    tr(
                        "База недоступна из локальной сети.",
                        "The database is not reachable from the local network.",
                    ),
                ],
                [
                    tr("Порты 5436 / 5437", "Ports 5436 / 5437"),
                    tr(
                        "Не конфликтуют с другими PostgreSQL на Mac (первый проект занимает 5433/5434).",
                        "No clash with other PostgreSQL on the Mac (the first project uses 5433/5434).",
                    ),
                ],
                [
                    tr("Образ по digest", "Image pinned by digest"),
                    tr(
                        "Тег postgres:17 могут перезаписать; digest — нет. Тот же digest в CI.",
                        "The postgres:17 tag can be overwritten; a digest cannot. CI uses the same digest.",
                    ),
                ],
                [
                    "healthcheck · pg_isready",
                    tr(
                        "--wait ждёт, пока база действительно примет соединения.",
                        "--wait blocks until the database really accepts connections.",
                    ),
                ],
                [
                    tr("Пароль из .env", "Password from .env"),
                    tr(
                        "Без .env Compose остановится с подсказкой; пароль не попадает в Git.",
                        "Without .env Compose stops with a hint; the password never reaches Git.",
                    ),
                ],
            ],
            [150, W - 150],
            [CELL, CELL],
        ),
        Spacer(1, 8),
        callout(
            tr(
                "<b>Проверено:</b> после docker compose down и нового up контейнер "
                "сменился, а 5 заказов и версия схемы 0001 остались в томе. "
                "<b>docker compose down -v удаляет том вместе с данными.</b>",
                "<b>Verified:</b> after docker compose down and a new up the container "
                "changed, while 5 orders and schema version 0001 stayed in the volume. "
                "<b>docker compose down -v deletes the volume with all data.</b>",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    # 13. Таблицы и связи
    section(
        story,
        13,
        tr(
            "Шесть таблиц, первичные и внешние ключи, связи «один ко многим».",
            "Six tables, primary and foreign keys, one-to-many relations.",
        ),
        BLUE,
    )
    story += [
        Diagram(262, er_diagram),
        Spacer(1, 12),
        simple_table(
            [tr("Таблица", "Table"), tr("Что хранит", "What it stores")],
            [
                [
                    mono("customers"),
                    tr(
                        "Клиенты — промышленные предприятия: регион и отрасль.",
                        "Customers — industrial companies: region and industry.",
                    ),
                ],
                [
                    mono("products"),
                    tr(
                        "Каталог: уникальный артикул, категория, себестоимость.",
                        "Catalogue: unique SKU, category, unit cost.",
                    ),
                ],
                [
                    mono("orders"),
                    tr(
                        "Заказ: клиент, статус, когда оформлен и когда оплачен.",
                        "Order: customer, status, when placed and when paid.",
                    ),
                ],
                [
                    mono("order_items"),
                    tr(
                        "Позиции: товар, количество, цена продажи, скидка.",
                        "Lines: product, quantity, sale price, discount.",
                    ),
                ],
                [
                    mono("refunds"),
                    tr(
                        "Возвраты денег по позиции и дата проведения.",
                        "Money refunds per line and when they were processed.",
                    ),
                ],
                [
                    mono("inventory_snapshots"),
                    tr(
                        "Остаток товара на конец дня.",
                        "Stock of a product at the end of a day.",
                    ),
                ],
            ],
            [130, W - 130],
            [CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            tr(
                "<b>Нормализация.</b> Один заказ — много товаров, поэтому заказ и позиции "
                "лежат в разных таблицах: клиент и дата оплаты хранятся один раз в orders, "
                "регион — один раз в customers. Цена продажи — в позиции, а не в товаре: "
                "в истории должна остаться цена, по которой продали.",
                "<b>Normalisation.</b> One order holds many products, so orders and lines "
                "are separate tables: the customer and payment date are stored once in "
                "orders, the region once in customers. The sale price sits on the line, "
                "not the product: history must keep the price actually charged.",
            ),
        ),
    ]

    # 14. Правила целостности
    section(
        story,
        14,
        tr(
            f"{counts['constraints']} именованных ограничений и {counts['indexes']} "
            "индексов: некорректную строку отвергнет сама PostgreSQL.",
            f"{counts['constraints']} named constraints and {counts['indexes']} "
            "indexes: PostgreSQL itself rejects an invalid row.",
        ),
        ORANGE,
    )
    story += [
        simple_table(
            [
                tr("Вид", "Kind"),
                tr("Сколько", "Count"),
                tr("Примеры в проекте", "Examples in the project"),
            ],
            [
                [
                    "CHECK",
                    str(counts["CheckConstraint"]),
                    tr(
                        "quantity &gt; 0; 0 ≤ discount &lt; 1; cost ≥ 0; amount &gt; 0; "
                        "у оплаченного заказа есть paid_at, у остальных нет; paid_at ≥ ordered_at",
                        "quantity &gt; 0; 0 ≤ discount &lt; 1; cost ≥ 0; amount &gt; 0; "
                        "paid orders have paid_at, others do not; paid_at ≥ ordered_at",
                    ),
                ],
                [
                    "UNIQUE",
                    str(counts["UniqueConstraint"]),
                    tr(
                        "артикул sku; один товар — одна строка заказа; один снимок в день",
                        "sku; one line per product per order; one snapshot per day",
                    ),
                ],
                [
                    "FOREIGN KEY",
                    str(counts["ForeignKeyConstraint"]),
                    tr(
                        "нельзя сослаться на несуществующего клиента, товар, заказ",
                        "no reference to a missing customer, product or order",
                    ),
                ],
                [
                    "PRIMARY KEY",
                    str(counts["PrimaryKeyConstraint"]),
                    tr("id каждой таблицы", "id of every table"),
                ],
                [
                    "NOT NULL",
                    "—",
                    tr("все столбцы, кроме paid_at", "every column except paid_at"),
                ],
            ],
            [96, 54, W - 150],
            [CELL, CELL, CELL],
        ),
        Spacer(1, 8),
        simple_table(
            [
                tr("Связь", "Relation"),
                tr("При удалении", "On delete"),
                tr("Почему", "Why"),
            ],
            [
                [
                    tr("заказ → позиции", "order → lines"),
                    "CASCADE",
                    tr(
                        "Позиции без заказа не имеют смысла.",
                        "Lines make no sense without their order.",
                    ),
                ],
                [
                    tr("клиент → заказы", "customer → orders"),
                    "RESTRICT",
                    tr(
                        "Клиента с историей продаж удалить нельзя.",
                        "A customer with sales history cannot be deleted.",
                    ),
                ],
                [
                    tr("товар → позиции, остатки", "product → lines, stock"),
                    "RESTRICT",
                    tr(
                        "Проданный товар остаётся в каталоге.",
                        "A sold product stays in the catalogue.",
                    ),
                ],
                [
                    tr("позиция → возвраты", "line → refunds"),
                    "RESTRICT",
                    tr(
                        "Проведённые деньги не исчезают; каскад удаления заказа упирается в возврат.",
                        "Processed money never vanishes; an order delete cascade stops at a refund.",
                    ),
                ],
            ],
            [140, 70, W - 210],
            [CELL, CELL, CELL],
        ),
        p(tr("Фактические ошибки PostgreSQL", "Actual PostgreSQL errors"), H2),
        code_block(PSQL_ERRORS),
        Spacer(1, 8),
        cards(
            [
                (
                    tr("Имена ограничений", "Constraint names"),
                    tr(
                        "Соглашение в app/db/base.py: ck_, fk_, uq_, ix_ + таблица + столбцы. По "
                        "имени из ошибки видно правило; тесты проверяют именно имя.",
                        "Convention in app/db/base.py: ck_, fk_, uq_, ix_ + table + columns. The "
                        "name in an error tells the rule; tests assert exactly that name.",
                    ),
                    BLUE,
                    BLUE_L,
                ),
                (
                    tr("Чего база не проверяет", "What the database does not check"),
                    tr(
                        "Правила между таблицами: сумма возвратов не больше позиции, возврат "
                        "только по оплаченному заказу. Их проверяет контроль качества этапа 03.",
                        "Cross-table rules: refunds not above the line total, refunds only for "
                        "paid orders. Stage 03 data quality checks cover them.",
                    ),
                    AMBER,
                    AMBER_L,
                ),
            ],
            columns=2,
        ),
    ]

    # 15. Деньги и время
    section(
        story,
        15,
        tr(
            "Почему деньги — NUMERIC и Decimal, а время — timestamptz и московский месяц.",
            "Why money is NUMERIC and Decimal, and time is timestamptz with Moscow months.",
        ),
        VIOLET,
    )
    story += [
        code_block(
            ">>> 0.1 + 0.2\n"
            "0.30000000000000004\n"
            ">>> from decimal import Decimal\n"
            '>>> Decimal("0.1") + Decimal("0.2")\n'
            "Decimal('0.3')"
        ),
        Spacer(1, 8),
        simple_table(
            [tr("Где", "Where"), tr("Тип", "Type"), tr("Смысл", "Meaning")],
            [
                [
                    tr("Цена, себестоимость, возврат", "Price, cost, refund"),
                    "NUMERIC(12, 2)",
                    tr(
                        "до 9 999 999 999.99 ₽ с точностью до копейки",
                        "up to 9,999,999,999.99 RUB to the kopeck",
                    ),
                ],
                [
                    tr("Скидка", "Discount"),
                    "NUMERIC(5, 4)",
                    tr("доля: 0.1250 = 12.5 %", "a fraction: 0.1250 = 12.5%"),
                ],
                [
                    "Python",
                    "Decimal",
                    tr(
                        "SQLAlchemy читает NUMERIC как Decimal",
                        "SQLAlchemy reads NUMERIC as Decimal",
                    ),
                ],
                [
                    tr("Сумма позиции", "Line amount"),
                    "ROUND(q × price × (1 − d), 2)",
                    tr(
                        "округление каждой позиции до копейки",
                        "each line rounded to the kopeck",
                    ),
                ],
            ],
            [140, 150, W - 290],
            [CELL, CELL, CELL],
        ),
        p(
            tr(
                "Слишком большое значение база отвергнет ошибкой numeric field overflow, "
                "а не исказит — это проверяет тест test_money_overflow_is_rejected.",
                "A too large value is rejected with numeric field overflow, not distorted "
                "— the test test_money_overflow_is_rejected checks it.",
            ),
            SMALL,
        ),
        p(tr("Один момент — два месяца", "One moment, two months"), H2),
        Diagram(132, timezone_timeline),
        Spacer(1, 10),
        callout(
            tr(
                "timestamptz хранит <b>момент</b>, а не «часы на стене». Заказ №5 оплачен "
                "1 октября в 01:30 по Москве = 30 сентября 22:30 UTC. Отчётный месяц "
                "компании — московский, поэтому запросы используют "
                + mono("AT TIME ZONE 'Europe/Moscow'")
                + ". По UTC сентябрь дал бы 328 000.00 вместо 310 000.00 — это "
                "проверяет тест test_month_depends_on_time_zone.",
                "timestamptz stores a <b>moment</b>, not a wall clock. Order 5 was paid "
                "on 1 October at 01:30 Moscow time = 30 September 22:30 UTC. The "
                "company's reporting month is Moscow time, so queries use "
                + mono("AT TIME ZONE 'Europe/Moscow'")
                + ". In UTC September would be 328,000.00 instead of 310,000.00 — the "
                "test test_month_depends_on_time_zone checks it.",
            ),
            VIOLET,
            VIOLET_L,
        ),
    ]

    # 16. SQLAlchemy и сессии
    section(
        story,
        16,
        tr(
            "Модели-классы описывают таблицы; пул и сессии управляют соединениями и "
            "транзакциями.",
            "Model classes describe tables; the pool and sessions manage connections and "
            "transactions.",
        ),
        BLUE,
    )
    story += [
        code_block(without_comments(class_source("app/db/models.py", "Order"))),
        Spacer(1, 8),
        simple_table(
            [tr("Элемент", "Element"), tr("Что означает", "Meaning")],
            [
                [
                    mono("Mapped[int]"),
                    tr(
                        "Тип для Python и mypy; без None — NOT NULL.",
                        "Type for Python and mypy; without None it is NOT NULL.",
                    ),
                ],
                [
                    mono("Mapped[datetime | None]"),
                    tr("Столбец может быть пустым (NULL).", "The column may be NULL."),
                ],
                [
                    mono("mapped_column(...)"),
                    tr(
                        "Тип в базе и ограничения столбца.",
                        "Database type and column rules.",
                    ),
                ],
                [
                    mono("__table_args__"),
                    tr(
                        "Ограничения и индексы всей таблицы.",
                        "Table-level constraints and indexes.",
                    ),
                ],
                [
                    mono("relationship(...)"),
                    tr(
                        "Связь объектов: order.customer, order.items. Это не столбец.",
                        "Object links: order.customer, order.items. Not a column.",
                    ),
                ],
            ],
            [160, W - 160],
            [CELL, CELL],
        ),
        p(tr("Пул соединений и сессии", "Connection pool and sessions"), H2),
        cards(
            [
                (
                    "Engine",
                    tr(
                        "Пул соединений. Создаётся лениво: импорт и /health базу не трогают. "
                        "pool_pre_ping отбрасывает разорванные соединения.",
                        "The connection pool. Created lazily: import and /health never touch the "
                        "database. pool_pre_ping drops broken connections.",
                    ),
                    BLUE,
                    BLUE_L,
                ),
                (
                    "Session",
                    tr(
                        "Рабочая область: flush() отправляет строки, commit() фиксирует, "
                        "rollback() отменяет всё в транзакции.",
                        "A unit of work: flush() sends rows, commit() makes them permanent, "
                        "rollback() undoes the whole transaction.",
                    ),
                    VIOLET,
                    VIOLET_L,
                ),
                (
                    tr("Транзакция", "Transaction"),
                    tr(
                        "Всё или ничего. Скрытого commit нет: код, который пишет данные, "
                        "фиксирует их сам.",
                        "All or nothing. There is no hidden commit: code that writes data "
                        "commits it explicitly.",
                    ),
                    GREEN,
                    GREEN_L,
                ),
            ]
        ),
    ]

    # 17. Миграции Alembic
    section(
        story,
        17,
        tr(
            "Схема меняется только миграциями: история, откат и одинаковая база у всех.",
            "The schema changes only through migrations: history, rollback and the same "
            "database for everyone.",
        ),
        VIOLET,
    )
    story += [
        Diagram(140, migration_flow),
        Spacer(1, 10),
        code_block(ALEMBIC_OUTPUT),
        Spacer(1, 8),
        simple_table(
            [tr("Команда", "Command"), tr("Что делает", "What it does")],
            [
                [
                    mono("alembic upgrade head"),
                    tr(
                        "Применить все неприменённые миграции",
                        "Apply all pending migrations",
                    ),
                ],
                [
                    mono("alembic downgrade -1"),
                    tr("Откатить одну миграцию", "Roll back one migration"),
                ],
                [
                    mono("alembic downgrade base"),
                    tr(
                        "Откатить всё — с удалением данных",
                        "Roll back everything — data is lost",
                    ),
                ],
                [
                    mono("alembic current"),
                    tr("Версия в базе", "Version in the database"),
                ],
                [mono("alembic history"), tr("Список миграций", "List of migrations")],
                [
                    mono("alembic check"),
                    tr(
                        "Есть ли изменения моделей без миграции",
                        "Are there model changes without a migration",
                    ),
                ],
                [
                    mono("alembic upgrade head --sql"),
                    tr("Показать SQL, не выполняя", "Show SQL without running it"),
                ],
            ],
            [190, W - 190],
            [CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            tr(
                "<b>Почему не create_all().</b> Он только создаёт отсутствующие таблицы и "
                "не меняет существующие. <b>Автогенерация — черновик</b>: файл читают "
                "глазами. <b>Применённую миграцию не редактируют</b> — любое изменение "
                "схемы оформляют новой миграцией 0002, 0003…",
                "<b>Why not create_all().</b> It only creates missing tables and never "
                "changes existing ones. <b>Autogenerate is a draft</b>: a human reads the "
                "file. <b>An applied migration is never edited</b> — every schema change "
                "is a new migration 0002, 0003…",
            ),
            VIOLET,
            VIOLET_L,
        ),
    ]

    # 18. /health и /ready
    section(
        story,
        18,
        tr(
            "Жив ли процесс и можно ли отправлять ему запросы — два разных вопроса.",
            "Whether the process is alive and whether it can take requests are two "
            "different questions.",
        ),
        GREEN,
    )
    story += [
        Diagram(122, ready_flow),
        Spacer(1, 10),
        simple_table(
            ["", "/health", "/ready"],
            [
                [
                    tr("Вопрос", "Question"),
                    tr("Процесс жив?", "Is the process alive?"),
                    tr("Можно принимать запросы?", "Can it take requests?"),
                ],
                [
                    tr("Обращается к базе", "Touches the database"),
                    tr("Нет", "No"),
                    tr(
                        "Да: соединение и версия схемы",
                        "Yes: connection and schema version",
                    ),
                ],
                [tr("Без базы", "Without a database"), "200", "503"],
                [
                    tr("Кому нужен", "Who uses it"),
                    tr("перезапуск упавшего процесса", "restarting a dead process"),
                    tr(
                        "решение, отправлять ли трафик",
                        "deciding whether to send traffic",
                    ),
                ],
            ],
            [130, (W - 130) / 2, (W - 130) / 2],
        ),
        p(
            tr(
                "Фактическая проверка на настоящем сервере",
                "Actual check on a real server",
            ),
            H2,
        ),
        code_block(READY_OUTPUT),
        Spacer(1, 8),
        callout(
            tr(
                "Третий ответ показывает pool_pre_ping: пул выбросил разорванные "
                "соединения и открыл новые без перезапуска API. Ответ 503 одинаков для "
                "всех причин — адрес базы и ошибки драйвера наружу не выходят.",
                "The third reply shows pool_pre_ping: the pool dropped broken connections "
                "and opened new ones without restarting the API. The 503 reply is the "
                "same for every cause — the database address and driver errors never "
                "leak out.",
            ),
            GREEN,
            GREEN_L,
        ),
    ]

    # 19. SQL вручную
    section(
        story,
        19,
        tr(
            "Четыре запроса на учебном наборе, все ответы посчитаны заранее.",
            "Four queries on the sample dataset; every answer was computed in advance.",
        ),
        TEAL,
    )
    story += [
        simple_table(
            [
                tr("Заказ", "Order"),
                tr("Статус", "Status"),
                tr("Состав", "Contents"),
                tr("Сумма", "Total"),
            ],
            [
                [
                    "1",
                    tr("оплачен 5 сен", "paid 5 Sep"),
                    tr(
                        "2 насоса × 100 000 − 10 %, 5 датчиков × 2 000",
                        "2 pumps × 100,000 − 10%, 5 sensors × 2,000",
                    ),
                    "190 000.00",
                ],
                [
                    "2",
                    tr("оплачен 20 сен", "paid 20 Sep"),
                    tr("1 насос × 120 000", "1 pump × 120,000"),
                    "120 000.00",
                ],
                [
                    "3",
                    tr("отменён", "cancelled"),
                    tr("10 кранов × 4 500", "10 valves × 4,500"),
                    "—",
                ],
                [
                    "4",
                    tr("не оплачен", "pending"),
                    tr("3 датчика × 2 000", "3 sensors × 2,000"),
                    "—",
                ],
                [
                    "5",
                    tr("оплачен 1 окт 01:30 МСК", "paid 1 Oct 01:30 MSK"),
                    tr("4 крана × 4 500", "4 valves × 4,500"),
                    "18 000.00",
                ],
            ],
            [44, 130, W - 254, 80],
            [CELL, CELL, CELL, CELL],
        ),
        p(
            tr(
                "Возвраты по датчикам заказа 1: 1 000.00 (10 сентября) и 500.00 "
                "(2 октября). Запуск файла: "
                + mono(
                    "docker compose exec -T db psql -U analyst -d industrialflow < sql/02_net_revenue_by_month.sql"
                ),
                "Refunds on the sensors of order 1: 1,000.00 (10 September) and 500.00 "
                "(2 October). Running a file: "
                + mono(
                    "docker compose exec -T db psql -U analyst -d industrialflow < sql/02_net_revenue_by_month.sql"
                ),
            ),
            SMALL,
        ),
        # Заголовок запроса держится вместе с его кодом и выводом на одной странице.
        KeepTogether(
            [
                p(
                    tr(
                        "01 · Суммы оплаченных заказов: JOIN и GROUP BY",
                        "01 · Paid order totals: JOIN and GROUP BY",
                    ),
                    H2,
                ),
                code_block(PSQL_ORDER_TOTALS),
                p(
                    tr(
                        "psql показывает время в UTC (+00): 09:00 UTC = 12:00 по Москве.",
                        "psql prints times in UTC (+00): 09:00 UTC = 12:00 Moscow time.",
                    ),
                    SMALL,
                ),
            ]
        ),
        KeepTogether(
            [
                p(
                    tr(
                        "02 · Чистая выручка по месяцам: CTE и FULL OUTER JOIN",
                        "02 · Net revenue by month: CTE and FULL OUTER JOIN",
                    ),
                    H2,
                ),
                code_block(sql_body("02_net_revenue_by_month.sql")),
                Spacer(1, 6),
                code_block(PSQL_NET_REVENUE),
                p(
                    tr(
                        "Правило курса: Net Revenue = Paid Sales − Processed Refunds; "
                        "возврат уменьшает выручку месяца, в котором проведён.",
                        "Course rule: Net Revenue = Paid Sales − Processed Refunds; a "
                        "refund reduces revenue of the month it is processed in.",
                    ),
                    SMALL,
                ),
            ]
        ),
        KeepTogether(
            [
                p(
                    tr(
                        "03 · Продажи по категориям: оконная функция",
                        "03 · Sales by category: a window function",
                    ),
                    H2,
                ),
                code_block(PSQL_CATEGORIES),
                p(
                    tr(
                        "SUM(...) OVER () видит итог по всем строкам результата, не "
                        "схлопывая их, — так считается доля категории.",
                        "SUM(...) OVER () sees the total of all result rows without "
                        "collapsing them — that is how a category share is computed.",
                    ),
                    SMALL,
                ),
            ]
        ),
        KeepTogether(
            [
                p(
                    tr(
                        "04 · Ловушка двойного подсчёта",
                        "04 · The double-counting trap",
                    ),
                    H2,
                ),
                Diagram(112, double_count),
                Spacer(1, 6),
                code_block(PSQL_DOUBLE_COUNT),
                Spacer(1, 6),
                callout(
                    tr(
                        "JOIN «один ко многим» повторяет строку позиции на каждый её "
                        "возврат: 338 000.00 вместо 328 000.00. Правило: сначала свести "
                        "таблицу «многих» к одной строке на ключ (или считать суммы "
                        "отдельно, как в запросе 02), потом соединять.",
                        "A one-to-many JOIN repeats the line for each of its refunds: "
                        "338,000.00 instead of 328,000.00. Rule: first reduce the “many” "
                        "table to one row per key (or sum separately, as query 02 does), "
                        "then join.",
                    ),
                    ORANGE,
                    ORANGE_L,
                ),
            ]
        ),
    ]

    # 20. Тесты с базой
    section(
        story,
        20,
        tr(
            f"{tests['unit']} unit-тестов без базы и {tests['integration']} "
            "интеграционных на настоящей PostgreSQL.",
            f"{tests['unit']} unit tests without a database and {tests['integration']} "
            "integration tests on a real PostgreSQL.",
        ),
        GREEN,
    )
    story += [
        Diagram(78, integration_fixtures),
        Spacer(1, 10),
        simple_table(
            [
                tr("Файл этапов 01–02", "Stage 01–02 file"),
                tr("Тестов", "Tests"),
                tr("Что проверяет", "What it checks"),
            ],
            [
                [
                    mono("test_config.py"),
                    "10",
                    tr(
                        "приоритет настроек; драйвер и имя базы; пароль скрыт",
                        "settings priority; driver and database name; password hidden",
                    ),
                ],
                [
                    mono("test_ready.py"),
                    "4",
                    tr(
                        "/ready без базы и с недоступной базой → 503",
                        "/ready without or with an unreachable database → 503",
                    ),
                ],
                [
                    mono("test_session.py"),
                    "3",
                    tr(
                        "ленивый пул, DatabaseNotConfigured",
                        "lazy pool, DatabaseNotConfigured",
                    ),
                ],
                [
                    mono("test_models.py"),
                    "5",
                    tr(
                        "6 таблиц, NUMERIC(12,2), правила удаления, имена",
                        "6 tables, NUMERIC(12,2), delete rules, names",
                    ),
                ],
                [
                    mono("integration/test_migrations.py"),
                    "5",
                    tr(
                        "upgrade, downgrade, alembic check, /ready",
                        "upgrade, downgrade, alembic check, /ready",
                    ),
                ],
                [
                    mono("integration/test_constraints.py"),
                    "23",
                    tr(
                        "20 плохих строк, каскад, Decimal, timestamptz",
                        "20 invalid rows, cascade, Decimal, timestamptz",
                    ),
                ],
                [
                    mono("integration/test_queries.py"),
                    "6",
                    tr(
                        "4 SQL-файла и часовой пояс на учебном наборе",
                        "4 SQL files and time zone on the sample data",
                    ),
                ],
            ],
            [190, 46, W - 236],
            [CELL, CELL, CELL],
        ),
        Spacer(1, 8),
        code_block(
            function_source(
                "tests/integration/test_constraints.py", "test_invalid_row_is_rejected"
            )
        ),
        Spacer(1, 8),
        code_block(
            "docker compose --profile test up --detach --wait db-test\n"
            "export TEST_DATABASE_URL=\\\n"
            "  'postgresql+psycopg://analyst:analyst_test@127.0.0.1:5437/industrialflow_test'\n"
            "uv run pytest\n"
            "uv run pytest -m integration"
        ),
        Spacer(1, 8),
        callout(
            tr(
                "Адрес — только из TEST_DATABASE_URL и только база *_test: тесты сбрасывают "
                "схему и не должны задеть базу разработки. Без адреса локально — skip "
                "интеграционных тестов, в CI (CI=true) — ошибка.",
                "The address comes only from TEST_DATABASE_URL and only a *_test database: "
                "tests reset the schema and must not touch the development database. "
                "Without it: integration tests skip locally and fail on CI (CI=true).",
            ),
            TEAL,
            TEAL_L,
        ),
    ]
