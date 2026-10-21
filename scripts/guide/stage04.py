"""Bilingual sections 24–26: exact metrics, comparisons and contributions."""

from reportlab.platypus import PageBreak, Spacer

from guide.i18n import tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BODY_S,
    CELL,
    H2,
    SMALL,
    TEAL,
    TEAL_L,
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


def add_stage04(story):
    """Add the analytics contract and a small hand-calculated teaching example."""
    section(
        story,
        24,
        tr(
            "SQL считает деньги; Python Decimal сохраняет точность результата.",
            "SQL computes money; Python Decimal preserves exact results.",
        ),
        TEAL,
    )
    story += [
        p(
            tr(
                "Этап 04 добавляет <b>app/analytics/</b> и JSON CLI без новых "
                "зависимостей. PostgreSQL и Decimal вычисляют показатели. LLM не "
                "участвует; Pandas и DuckDB отложены по ADR 0004.",
                "Stage 04 adds <b>app/analytics/</b> and a JSON CLI without new "
                "dependencies. PostgreSQL and Decimal compute the metrics. No "
                "LLM is involved; ADR 0004 defers Pandas and DuckDB.",
            )
        ),
        Spacer(1, 8),
        simple_table(
            [tr("Поле", "Field"), tr("Правило", "Rule")],
            [
                [
                    mono("paid_sales"),
                    tr(
                        "Продажи оплаченных заказов по paid_at.",
                        "Paid-order sales recognised by paid_at.",
                    ),
                ],
                [
                    mono("refunds"),
                    tr(
                        "Возвраты по processed_at, только по оплаченным заказам.",
                        "Refunds by processed_at, only on paid orders.",
                    ),
                ],
                [mono("net_revenue"), mono("paid_sales − refunds")],
                [
                    mono("paid_orders"),
                    tr("Каждый оплаченный заказ один раз.", "Each paid order once."),
                ],
                [
                    mono("average_order_value"),
                    tr(
                        "Продажи / заказы, до возвратов; null без оплат.",
                        "Sales / orders, before refunds; null without paid orders.",
                    ),
                ],
            ],
            [160, W - 160],
            [CELL, CELL],
        ),
        p(tr("Период и округление", "Periods and rounding"), H2),
        p(
            tr(
                "<b>[start, end)</b> — даты в Europe/Moscow: начало включено, конец "
                "исключён. Сентябрь: 2026-09-01 → 2026-10-01. Каждая позиция "
                "округляется до копеек <b>до суммирования</b>: "
                "ROUND(quantity × unit_price × (1 − discount), 2). "
                "Деньги — NUMERIC/Decimal, в рублях без НДС.",
                "<b>[start, end)</b> uses Europe/Moscow dates: start included, end "
                "excluded. September: 2026-09-01 → 2026-10-01. Each line is rounded "
                "to two decimal places <b>before summing</b>: "
                "ROUND(quantity × unit_price × (1 − discount), 2). "
                "Money is NUMERIC/Decimal, in RUB excluding VAT.",
            )
        ),
        Spacer(1, 8),
        callout(
            tr(
                "<b>Продажи и возвраты агрегируются отдельно.</b> Несколько "
                "возвратов не повторяют продажу. Заказы считаются из orders, "
                "а не из строк JOIN. Октябрьский возврат сентябрьской покупки "
                "уменьшает октябрьскую выручку.",
                "<b>Sales and refunds use separate aggregates.</b> Multiple "
                "refunds cannot duplicate a sale. Orders are counted from orders, "
                "not joined lines. An October refund for a September purchase "
                "reduces October revenue.",
            )
        ),
        Spacer(1, 8),
        code_block(
            "uv run python -m app.analytics \\\n  --start 2026-09-01 --end 2026-10-01"
        ),
        p(
            tr(
                "JSON: суммы строками, неопределённые значения null. Все запросы "
                "CLI видят один снимок в транзакции REPEATABLE READ READ ONLY. "
                "DATABASE_URL берётся из настроек; сервер API не нужен.",
                "JSON uses decimal strings and null for undefined values. All "
                "CLI queries share one snapshot in a REPEATABLE READ READ ONLY "
                "transaction. DATABASE_URL comes from settings; no API server is needed.",
            ),
            SMALL,
        ),
    ]

    section(
        story,
        25,
        tr(
            "Пустые месяцы остаются в ряду; нулевой знаменатель не даёт процент.",
            "Empty months stay in the series; a zero denominator gives no percentage.",
        ),
        VIOLET,
    )
    story += [
        p(
            tr(
                "<b>monthly_metrics</b> строит календарные отрезки, включая пустые "
                "месяцы. Частичные первый и последний месяцы обрезаны границами "
                "запроса; максимум 120 отрезков. Нет оплат — средний чек null. "
                "Только возвраты — выручка может быть отрицательной.",
                "<b>monthly_metrics</b> creates calendar buckets, including empty "
                "months. Partial first and last months are clipped to the request; "
                "the limit is 120 buckets. No paid orders means null AOV. "
                "Refund-only periods can have negative net revenue.",
            )
        ),
        p(tr("Ручной пример: app.db.sample", "Manual example: app.db.sample"), H2),
        simple_table(
            [
                tr("Показатель", "Metric"),
                tr("Сентябрь", "September"),
                tr("Октябрь", "October"),
            ],
            [
                [tr("Продажи", "Paid sales"), "310000.00", "18000.00"],
                [tr("Возвраты", "Refunds"), "1000.00", "500.00"],
                [tr("Чистая выручка", "Net revenue"), "309000.00", "17500.00"],
                [tr("Оплаченные заказы", "Paid orders"), "2", "1"],
                [tr("Средний чек", "Average order value"), "155000.00", "18000.00"],
            ],
            [235, (W - 235) / 2, (W - 235) / 2],
        ),
        p(
            tr(
                "Это маленький набор этапа 02, <b>не demo из 20 000 заказов</b>. "
                "В октябре есть возврат 500.00 по сентябрьской продаже.",
                "This is the small Stage 02 fixture, <b>not the 20,000-order demo</b>. "
                "October includes a 500.00 refund for a September sale.",
            ),
            SMALL,
        ),
        Spacer(1, 7),
        code_block(
            "uv run python -m app.analytics \\\n"
            "  --start 2026-10-01 --end 2026-11-01 \\\n"
            "  --compare-start 2026-09-01 --compare-end 2026-10-01 \\\n"
            "  --dimension category"
        ),
        p(tr("Разница и процент", "Absolute and percentage changes"), H2),
        p(
            tr(
                "Разница = current − previous. Процент = разница / abs(previous) "
                "× 100, округление ROUND_HALF_UP до двух знаков. Выручка: "
                "17500 − 309000 = <b>−291500.00 (−94.34%)</b>. Прошлый показатель "
                "−100, текущий −50: улучшение +50%.",
                "Delta = current − previous. Percentage = delta / abs(previous) "
                "× 100, rounded to two places with ROUND_HALF_UP. Net revenue: "
                "17500 − 309000 = <b>−291500.00 (−94.34%)</b>. A baseline of "
                "−100 and current −50 means a +50% improvement.",
            )
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>previous = 0 → процент null.</b> Если среднего чека нет хотя "
                "бы в одном периоде, его сравнение тоже null. Периоды сравниваются "
                "по суммам: разная длина не пересчитывается в показатель «на день».",
                "<b>previous = 0 → null percentage.</b> If either period has no "
                "AOV, its comparison is also null. Totals are compared as given: "
                "different period lengths are not normalised per day.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    section(
        story,
        26,
        tr(
            "Вклад объясняет арифметику изменения, а не причину поведения покупателей.",
            "Contributions explain the arithmetic of change, not customer behaviour.",
        ),
        TEAL,
    )
    story += [
        p(
            tr(
                "Измерения из разрешённого списка: <b>category</b> — категория "
                "товара, <b>region</b> — регион клиента. Группы берутся из обоих "
                "периодов, включая группы только с возвратами. Сортировка: "
                "разница по возрастанию, затем название.",
                "Allowed dimensions: <b>category</b> is the product category; "
                "<b>region</b> is the customer's region. Groups come from both "
                "periods, including refund-only groups. Sort order is delta "
                "ascending, then name.",
            )
        ),
        Spacer(1, 8),
        callout(
            tr(
                "<b>Вклад, % = разница выручки группы / общая разница × 100.</b> "
                "Знаки сохраняются. Нулевая общая разница даёт null для всех долей.",
                "<b>Contribution, % = group net delta / total net delta × 100.</b> "
                "Signs are preserved. Zero total change gives null for every share.",
            )
        ),
        p(
            tr(
                "Октябрь к сентябрю: учебный набор",
                "October vs September: sample fixture",
            ),
            H2,
        ),
        simple_table(
            [
                tr("Категория", "Category"),
                tr("Разница, RUB", "Delta, RUB"),
                tr("Вклад", "Share"),
            ],
            [
                [tr("Насосы", "Pumps"), "−300000.00", "102.92%"],
                [tr("Датчики", "Sensors"), "−9500.00", "3.26%"],
                [tr("Запорная арматура", "Valves"), "+18000.00", "−6.17%"],
                [tr("Всего", "Total"), "−291500.00", "100.01%"],
            ],
            [235, 150, W - 385],
        ),
        p(
            tr(
                "Насосы дают больше 100% падения: арматура частично его "
                "компенсирует и имеет отрицательный вклад в общее снижение. "
                "Датчики остаются в октябре только с возвратом. После округления "
                "сумма долей 100.01%, а не ровно 100% — это допустимо.",
                "Pumps account for more than 100% of the decline: valves offset "
                "part of it and have a negative share of the overall decrease. "
                "Sensors remain in October through a refund only. Rounded shares "
                "sum to 100.01% rather than exactly 100%; this is expected.",
            )
        ),
        Spacer(1, 8),
        code_block(
            "uv run pytest tests/test_analytics_models.py \\\n"
            "  tests/test_analytics_cli.py\n"
            "uv run pytest tests/integration/test_analytics.py"
        ),
        p(
            tr(
                "Интеграционные тесты — только TEST_DATABASE_URL с суффиксом "
                "_test. Проверяются ручные суммы, двойной счёт, округление, "
                "Московские границы, пустые месяцы, сравнения и вклады. "
                f"Фактические результаты — раздел {RESULTS} и docs/VERIFICATION.md.",
                "Integration tests use TEST_DATABASE_URL ending in _test only. "
                "They cover manual totals, double counting, rounding, Moscow "
                "boundaries, empty months, comparisons and contributions. "
                f"Actual outcomes are in section {RESULTS} and docs/VERIFICATION.md.",
            ),
            SMALL,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Следующие этапы:</b> поиск аномалий — 05; REST API метрик — 06; "
                "LLM-агент — 07. Изменение выручки по группе само по себе "
                "не доказывает причину падения.",
                "<b>Following stages:</b> anomaly detection is Stage 05; the metrics REST API "
                "is Stage 06; the LLM agent is Stage 07. A group's revenue change "
                "alone does not prove why sales fell.",
            ),
            VIOLET,
            VIOLET_L,
        ),
    ]
    add_demo_results(story)


# Записанный вывод python -m app.analytics на data/demo (seed 42) от 2026-10-21:
# сентябрь против августа. Набор воспроизводим, числа повторяет та же команда.
DEMO_SUMMARY = [
    (
        ("Продажи", "Paid sales"),
        "633 733 255.24",
        "468 349 280.42",
        "−165 383 974.82 (−26.10%)",
    ),
    (("Возвраты", "Refunds"), "1 557 126.03", "1 670 523.07", "+113 397.04 (+7.28%)"),
    (
        ("Чистая выручка", "Net revenue"),
        "632 176 129.21",
        "466 678 757.35",
        "−165 497 371.86 (−26.18%)",
    ),
    (("Оплаченные заказы", "Paid orders"), "1 985", "1 931", "−54 (−2.72%)"),
    (
        ("Средний чек", "Average order value"),
        "319 261.09",
        "242 542.35",
        "−76 718.74 (−24.03%)",
    ),
]
DEMO_CATEGORIES = [
    ("pumps", "−138 597 069.79", "83.75%"),
    ("compressors", "−26 317 759.86", "15.90%"),
    ("sensors", "−294 972.94", "0.18%"),
    ("valves", "−287 569.27", "0.17%"),
]


def add_demo_results(story):
    """Полный набор seed 42: сентябрь к августу и вклад категорий."""
    story += [
        PageBreak(),
        p(
            tr(
                "Полный набор seed 42: сентябрь к августу",
                "Full seed 42 dataset: September vs August",
            ),
            H2,
        ),
        p(
            tr(
                "Тот же CLI на 20 000 заказах этапа 03, загруженных в отдельную пустую "
                "базу *_test. Фактический вывод 21 октября 2026 года:",
                "The same CLI on the 20,000 Stage 03 orders loaded into a separate "
                "empty *_test database. Actual output on 21 October 2026:",
            ),
            BODY_S,
        ),
        Spacer(1, 6),
        code_block(
            "uv run python -m app.analytics \\\n"
            "  --start 2026-09-01 --end 2026-10-01 \\\n"
            "  --compare-start 2026-08-01 --compare-end 2026-09-01 \\\n"
            "  --dimension category"
        ),
        Spacer(1, 8),
        simple_table(
            [
                tr("Показатель", "Metric"),
                tr("Август", "August"),
                tr("Сентябрь", "September"),
                tr("Изменение", "Change"),
            ],
            [[tr(*name), aug, sep, change] for name, aug, sep, change in DEMO_SUMMARY],
            [118, 112, 112, W - 342],
            [CELL, CELL, CELL, CELL],
        ),
        Spacer(1, 8),
        simple_table(
            [
                tr("Категория", "Category"),
                tr("Разница выручки", "Net delta"),
                tr("Вклад", "Share"),
            ],
            [list(row) for row in DEMO_CATEGORIES],
            [150, 180, W - 330],
            [CELL, CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            tr(
                "<b>Это сценарий A01.</b> Заказов почти столько же (−2.72%), а средний "
                "чек упал на 24%: насосов покупают меньше. Насосы дают 83.75% падения "
                "выручки. Аналитика нашла это, не читая ground_truth.json. По регионам "
                "падение распределено ровно: от 7.72% (Ural) до 18.56% (Central).",
                "<b>This is scenario A01.</b> Order count barely moved (−2.72%) while "
                "average order value fell 24%: fewer pumps are bought. Pumps account "
                "for 83.75% of the revenue decline. The analytics found it without "
                "reading ground_truth.json. By region the decline is spread evenly, "
                "from 7.72% (Ural) to 18.56% (Central).",
            ),
            TEAL,
            TEAL_L,
        ),
        Spacer(1, 8),
        callout(
            tr(
                "Помесячный ряд январь–сентябрь показывает и сценарий <b>A03</b>: "
                "возвраты июля 132 586 941.37 при 0.8–1.7 млн в другие месяцы. "
                "Это измерение, а не объяснение: почему упали насосы (склад, цена, "
                "спрос), из этих чисел не следует. Автоматический поиск отклонений — "
                "этап 05.",
                "The January–September monthly series also shows scenario <b>A03</b>: "
                "July refunds of 132,586,941.37 against 0.8–1.7 million in other "
                "months. This is measurement, not explanation: why pumps fell "
                "(stock, price, demand) does not follow from these numbers. "
                "Automatic detection of deviations is Stage 05.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]
