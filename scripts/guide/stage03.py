"""Bilingual sections 21–23: reproducible demo data, scenarios and safe loading."""

from reportlab.platypus import Spacer

from guide.i18n import tr
from guide.layout import (
    AMBER,
    AMBER_L,
    CELL,
    H2,
    SMALL,
    TEAL,
    VIOLET,
    VIOLET_L,
    W,
    callout,
    code_block,
    mono,
    p,
    simple_table,
)
from guide.toc import number_of, section

# Номер раздела с итогами: при вставке новых разделов он сдвигается сам.
RESULTS = number_of("Итоги проверки")


def add_stage03(story):
    """Add three compact teaching pages without inventing verification results."""
    section(
        story,
        21,
        tr(
            "Один seed и те же параметры дают одинаковые файлы без подключения к базе.",
            "The same seed and parameters produce identical files without a database.",
        ),
        TEAL,
    )
    story += [
        p(
            tr(
                "Новый набор для IndustrialFlow: <b>20 000 заказов, 640 клиентов, "
                "64 товара, 8 регионов</b>, январь–сентябрь 2026 года. Компания и "
                "операции вымышлены. Месяцы считаются по Europe/Moscow.",
                "The IndustrialFlow demo has <b>20,000 orders, 640 customers, "
                "64 products and 8 regions</b> for January–September 2026. The "
                "company and transactions are fictional. Reporting months use "
                "Europe/Moscow.",
            )
        ),
        Spacer(1, 8),
        code_block(
            "uv run python -m app.data.generate \\\n"
            "  --output data/demo --seed 42 --orders 20000"
        ),
        Spacer(1, 8),
        callout(
            tr(
                "<b>Каталог должен быть новым или пустым.</b> Генератор не "
                "перезаписывает существующий набор. Для повторного запуска выбери "
                "другой путь, например data/demo-repeat.",
                "<b>The output directory must be new or empty.</b> The generator "
                "refuses to overwrite a bundle. Use another path for a repeat run, "
                "such as data/demo-repeat.",
            )
        ),
        p(tr("Что появляется в каталоге", "What the output directory contains"), H2),
        simple_table(
            [tr("Файл", "File"), tr("Содержание", "Contents")],
            [
                [
                    mono("customers.csv, products.csv"),
                    tr(
                        "Клиенты и каталог товаров.",
                        "Customers and the product catalogue.",
                    ),
                ],
                [
                    mono("orders.csv, order_items.csv"),
                    tr("Заказы и позиции заказов.", "Orders and their lines."),
                ],
                [
                    mono("refunds.csv"),
                    tr("Проведённые возвраты денег.", "Processed monetary refunds."),
                ],
                [
                    mono("inventory_snapshots.csv"),
                    tr("Ежедневные остатки товаров.", "Daily product stock snapshots."),
                ],
                [
                    mono("manifest.json"),
                    tr(
                        "Версия формата, seed, число строк и контрольные суммы CSV.",
                        "Schema version, seed, row counts and CSV integrity hashes.",
                    ),
                ],
                [
                    mono("ground_truth.json"),
                    tr(
                        "Исходные и изменённые показатели сценариев, только для оценки.",
                        "Baseline and observed scenario evidence, for evaluation only.",
                    ),
                ],
            ],
            [235, W - 235],
            [CELL, CELL],
        ),
        p(tr("Почему результат повторяется", "Why the result repeats"), H2),
        p(
            tr(
                "Свой random.Random(seed) задаёт последовательность выборок. "
                "Decimal считает деньги, CSV хранит их десятичным текстом. NumPy "
                "и Faker не нужны. Те же параметры и версия генератора дают "
                "одинаковые байты; другой seed меняет конкретные заказы.",
                "A local random.Random(seed) defines the sampling sequence. "
                "Decimal computes money, and CSV stores decimal text. NumPy and "
                "Faker are unnecessary. The same parameters and generator version "
                "give equal bytes; a different seed changes individual orders.",
            )
        ),
        Spacer(1, 7),
        code_block(
            "uv run python -m app.data.generate \\\n"
            "  --output data/demo-repeat --seed 42 --orders 20000\n"
            "diff -r data/demo data/demo-repeat"
        ),
        p(
            tr(
                "diff без различий и с кодом 0 подтверждает совпадение. "
                "Сгенерированные наборы не включаются в Git.",
                "No diff output and exit code 0 confirm equal files. Generated "
                "bundles are excluded from Git.",
            ),
            SMALL,
        ),
    ]

    section(
        story,
        22,
        tr(
            "Необычное деловое событие может полностью соблюдать правила данных.",
            "An unusual business event can fully satisfy the data integrity rules.",
        ),
        VIOLET,
    )
    story += [
        p(
            tr(
                "Генератор сначала создаёт исходные данные, затем внедряет пять "
                "сценариев. Это <b>валидные операции</b>, которые должны проходить "
                "проверку качества. Позднее аналитика должна обнаружить их "
                "проявления в таблицах.",
                "The generator first creates baseline data, then injects five "
                "scenarios. These are <b>valid transactions</b> that must pass "
                "quality checks. Later analytics must find their effects in the "
                "database tables.",
            )
        ),
        Spacer(1, 8),
        simple_table(
            ["ID", tr("Когда и где", "When and where"), tr("Изменение", "Change")],
            [
                [
                    "A01",
                    tr("Сентябрь, оплаченные насосы", "September, paid pump lines"),
                    tr(
                        "Количество = 40% исходного, округление вниз, минимум 1.",
                        "Quantity = 40% of baseline, rounded down, minimum 1.",
                    ),
                ],
                [
                    "A02",
                    tr("Август, Юг, оплаченная арматура", "August, South, paid valves"),
                    tr("Скидка 35%.", "A 35% discount."),
                ],
                [
                    "A03",
                    tr("Июль, оплаченные компрессоры", "July, paid compressor lines"),
                    tr(
                        "Дополнительный возврат 30% округлённой суммы позиции.",
                        "An extra refund of 30% of the rounded line amount.",
                    ),
                ],
                [
                    "A04",
                    tr("10–19 сентября, насос с ID 1", "10–19 September, pump ID 1"),
                    tr("Остаток равен нулю.", "Inventory snapshot quantity is zero."),
                ],
                [
                    "A05",
                    tr(
                        "Одна оплаченная позиция датчиков в июне",
                        "One paid sensor line in June",
                    ),
                    tr("Количество равно 500.", "Quantity is 500."),
                ],
            ],
            [36, 175, W - 211],
        ),
        Spacer(1, 10),
        callout(
            tr(
                "<b>A01 и A04 не доказывают причинность.</b> Снижение количества "
                "насосов и нулевой остаток одного товара совпадают по времени. "
                "Это повод проверить гипотезу, а не готовый вывод о причине.",
                "<b>A01 and A04 do not prove causation.</b> Reduced pump quantities "
                "and zero stock for one product overlap in time. That motivates "
                "a hypothesis to test, not a proven explanation.",
            ),
            AMBER,
            AMBER_L,
        ),
        p(tr("Что такое ответ для оценки", "What the evaluation answer key means"), H2),
        p(
            tr(
                "ground_truth.json хранит исходные и наблюдаемые величины, "
                "вычисленные кодом. Он нужен тестам и будущей оценке аналитики. "
                "<b>Будущий LLM-агент его не читает:</b> агент должен получать "
                "числа из SQL/Python-инструментов поверх базы.",
                "ground_truth.json stores baseline and observed values computed "
                "by code. Tests and later analytics evaluation use it. <b>The "
                "future LLM agent must not read it:</b> it must obtain numbers "
                "from SQL/Python tools over the database.",
            )
        ),
        Spacer(1, 8),
        callout(
            tr(
                "<b>Различай два вопроса.</b> «Возвраты больше стоимости позиции?» "
                "— проверка корректности. «Почему возвратов стало больше?» — "
                "аналитический вопрос. Успешная проверка качества не исключает "
                "необычных событий бизнеса.",
                "<b>Separate two questions.</b> “Do refunds exceed the line amount?” "
                "checks validity. “Why did refunds rise?” is an analytics question. "
                "Passing quality checks does not rule out unusual business events.",
            ),
            VIOLET,
            VIOLET_L,
        ),
    ]

    section(
        story,
        23,
        tr(
            "Одна транзакция для импорта; отдельная команда только читает базу.",
            "One transaction imports the bundle; a separate command only reads it.",
        ),
        TEAL,
    )
    story += [
        code_block(
            "docker compose up --detach --wait db\n"
            "uv run alembic upgrade head\n"
            "uv run python -m app.data.load --input data/demo\n"
            "uv run python -m app.data.quality"
        ),
        Spacer(1, 8),
        callout(
            tr(
                "<b>Все шесть таблиц должны быть пустыми.</b> Маленький набор "
                "app.db.sample и полный demo выбираются до загрузки. При "
                "существующих строках загрузчик отказывает; параметра сброса нет.",
                "<b>All six domain tables must be empty.</b> Choose the small "
                "app.db.sample dataset or the full demo before loading. The "
                "loader refuses existing rows and provides no reset option.",
            ),
            AMBER,
            AMBER_L,
        ),
        p(tr("Что защищает загрузку", "What protects the import"), H2),
        p(
            tr(
                "Проверка комплекта и манифеста выявляет неполные или изменённые "
                "файлы. Клиенты и товары загружаются до ссылающихся на них строк. "
                "Одна транзакция фиксирует весь набор; при ошибке импорт "
                "откатывается целиком. Обычные команды берут DATABASE_URL из "
                "настроек проекта.",
                "Bundle and manifest validation detect incomplete or changed "
                "files. Customers and products are imported before rows that "
                "reference them. One transaction commits the entire bundle; an "
                "error rolls it all back. Normal CLI commands use DATABASE_URL "
                "from the project settings.",
            )
        ),
        p(tr("Что проверяет quality", "What quality checks"), H2),
        simple_table(
            [tr("Правило", "Rule"), tr("Пример нарушения", "Violation example")],
            [
                [
                    tr("В каждом заказе есть позиции", "Every order has lines"),
                    tr(
                        "Есть заказ, у которого нет ни одной позиции.",
                        "An order exists without any order lines.",
                    ),
                ],
                [
                    tr(
                        "Сумма возвратов ≤ сумма позиции", "Total refunds ≤ line amount"
                    ),
                    tr(
                        "Позиция 100.00, два возврата по 60.00 = 120.00.",
                        "A 100.00 line has two 60.00 refunds, totalling 120.00.",
                    ),
                ],
                [
                    tr("Возврат только по оплате", "Refund only for a paid order"),
                    tr(
                        "Возврат у pending или cancelled.",
                        "A refund on a pending or cancelled order.",
                    ),
                ],
                [
                    tr("Возврат не раньше оплаты", "Refund is not before payment"),
                    tr(
                        "Оплата 12 июля, возврат 11 июля.",
                        "Payment on 12 July, refund on 11 July.",
                    ),
                ],
            ],
            [210, W - 210],
        ),
        Spacer(1, 8),
        p(
            tr(
                "Сумма позиции = ROUND(quantity × unit_price × (1 − discount), 2). "
                "quality не меняет строки: код 0 — правила прошли, 1 — найдены "
                "нарушения. Ограничения PostgreSQL продолжают защищать отдельные "
                "строки, внешние ключи и уникальность.",
                "Line amount = ROUND(quantity × unit_price × (1 − discount), 2). "
                "quality never changes rows: exit 0 means the rules passed; exit "
                "1 means violations were found. PostgreSQL constraints continue "
                "to guard row validity, foreign keys and uniqueness.",
            ),
            SMALL,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Интеграционные тесты:</b> только TEST_DATABASE_URL и база с "
                "суффиксом _test. Базу разработки из .env тесты не используют. "
                "Фактические результаты — в разделе 34 и docs/VERIFICATION.md; "
                "удалённый GitHub Actions подтверждается отдельно.",
                "<b>Integration tests:</b> TEST_DATABASE_URL only, with a database "
                "name ending in _test. Tests never use the development .env "
                f"database. Actual results are in section {RESULTS} and "
                "docs/VERIFICATION.md; remote GitHub Actions is confirmed separately.",
            )
        ),
    ]
