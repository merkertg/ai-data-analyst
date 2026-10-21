"""Bilingual sections 30–32: REST API, sessions and errors, saved reports."""

from reportlab.platypus import Spacer

from guide.diagrams import api_flow
from guide.i18n import tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BLUE,
    BODY_S,
    CELL,
    GREEN,
    GREEN_L,
    H2,
    SMALL,
    VIOLET,
    VIOLET_L,
    Diagram,
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


def add_stage06(story):
    """Explain the HTTP layer, lazy sessions, error codes and report snapshots."""
    section(
        story,
        number_of("REST API и параметры"),
        tr(
            "Тонкий HTTP-слой над готовой аналитикой: числа считает ядро.",
            "A thin HTTP layer over the existing analytics: the core computes numbers.",
        ),
        BLUE,
    )
    story += [
        p(
            tr(
                "Этап 06 открывает показатели этапов 04–05 по HTTP: одним JSON "
                "пользуются интерфейс (08) и агент (07). Маршрут в "
                "<b>app/api/</b> только принимает запрос, сервис в "
                "<b>app/services/</b> собирает ответ из функций "
                "<b>app/analytics/</b>. Ни маршрут, ни сервис деньги не считают.",
                "Stage 06 exposes the Stage 04–05 results over HTTP: the UI (08) "
                "and the agent (07) share one JSON format. A route in "
                "<b>app/api/</b> only accepts the request; a service in "
                "<b>app/services/</b> arranges the answer from <b>app/analytics/</b> "
                "functions. Neither computes money itself.",
            )
        ),
        Diagram(112, api_flow),
        Spacer(1, 4),
        simple_table(
            [tr("Метод и путь", "Method and path"), tr("Что возвращает", "Returns")],
            [
                [
                    mono("GET /api/metrics/revenue"),
                    tr(
                        "Продажи, возвраты, чистая выручка, месяцы, сравнение.",
                        "Sales, refunds, net revenue, months, comparison.",
                    ),
                ],
                [
                    mono("GET /api/metrics/orders"),
                    tr(
                        "Оплаченные заказы и средний чек.",
                        "Paid orders and average order value.",
                    ),
                ],
                [
                    mono("GET /api/analytics/categories"),
                    tr(
                        "Изменение выручки и вклад каждой категории.",
                        "Revenue change and each category's contribution.",
                    ),
                ],
                [
                    mono("GET /api/analytics/regions"),
                    tr("То же по регионам клиентов.", "The same by customer region."),
                ],
                [
                    mono("GET /api/analytics/anomalies"),
                    tr("Кандидаты этапа 05.", "Stage 05 candidates."),
                ],
                [
                    mono("POST /api/reports"),
                    tr("Посчитать и сохранить отчёт.", "Compute and save a report."),
                ],
                [
                    mono("GET /api/reports/{id}"),
                    tr("Сохранённый отчёт как есть.", "A saved report as stored."),
                ],
            ],
            [200, W - 200],
            [CELL, CELL],
        ),
        p(tr("Параметры — модель Pydantic", "Parameters are a Pydantic model"), H2),
        code_block(
            '@router.get("/revenue", responses=DATABASE_RESPONSES)\n'
            "def revenue(\n"
            "    session: ReadSession, query: Annotated[OptionalComparisonQuery, Query()]\n"
            ") -> RevenueResponse:\n"
            "    return analytics.revenue(session, query)"
        ),
        Spacer(1, 6),
        p(
            tr(
                "Query() раскладывает поля модели по параметрам строки запроса. "
                "Период полуоткрытый, по Москве: start=2026-09-01&amp;end=2026-10-01 — "
                "сентябрь. Правила: start &lt; end, не больше 120 календарных "
                "месяцев, compare_start и compare_end — вместе или никак, seed "
                '0–4294967295. Неизвестный параметр (extra="forbid") — тоже 422: '
                "опечатка не превращается в молча проигнорированный фильтр.",
                "Query() maps model fields to query string parameters. A period is "
                "half-open in Moscow time: start=2026-09-01&amp;end=2026-10-01 is "
                "September. Rules: start &lt; end, at most 120 calendar months, "
                "compare_start and compare_end together or not at all, seed "
                '0–4294967295. An unknown parameter (extra="forbid") is also a 422, '
                "so a typo never becomes a silently ignored filter.",
            ),
            BODY_S,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Деньги — строки JSON.</b> Pydantic выводит Decimal как "
                '"466678757.35": число с плавающей точкой у клиента не теряет '
                "копейки. Неопределённое значение (средний чек без заказов, процент "
                "от нулевой базы) — null. В каждом ответе есть "
                '"currency": "RUB" и "timezone": "Europe/Moscow".',
                "<b>Money is a JSON string.</b> Pydantic writes Decimal as "
                '"466678757.35", so a client float never loses kopecks. An undefined '
                "value (AOV without orders, a percentage of a zero baseline) is "
                'null. Every response states "currency": "RUB" and '
                '"timezone": "Europe/Moscow".',
            ),
        ),
    ]

    section(
        story,
        number_of("Сессии и ошибки"),
        tr(
            "Один снимок данных на запрос; ошибки базы не раскрываются клиенту.",
            "One data snapshot per request; database errors never reach the client.",
        ),
        VIOLET,
    )
    story += [
        p(
            tr(
                "Маршрут объявляет, что ему нужно, а FastAPI вызывает зависимость "
                "через Depends. <b>ReadSession</b> для всех GET — транзакция "
                "REPEATABLE READ READ ONLY: все запросы одного ответа видят одни "
                "данные, а запись отклоняет сама PostgreSQL. <b>WriteSession</b> "
                "нужна для сохранения отчётов и запусков агента; commit явный, "
                "ошибка откатывает транзакцию. Тесты подменяют обе через "
                "app.dependency_overrides сессией базы *_test.",
                "A route declares what it needs and FastAPI calls the dependency "
                "through Depends. <b>ReadSession</b> for every GET is a REPEATABLE "
                "READ READ ONLY transaction: all queries of one response see the "
                "same data and PostgreSQL itself rejects writes. <b>WriteSession</b> "
                "stores reports and agent runs; the code commits explicitly "
                "and an error rolls back. Tests replace both through "
                "app.dependency_overrides with a *_test database session.",
            ),
            BODY_S,
        ),
        p(
            tr(
                "Находка: зависимости выполняются до проверки",
                "Finding: dependencies run before validation fails",
            ),
            H2,
        ),
        p(
            tr(
                "Первая версия открывала обычную Session. Тесты показали, что "
                "FastAPI вызывает зависимости, даже когда параметры неверны. "
                "Без DATABASE_URL запрос с end ≤ start получал 503 вместо 422, "
                "а с базой — лишнее соединение. Исправление — <b>LazySession</b>: "
                "engine выбирается при первом SQL и сохраняется. Один bind "
                "нужен, чтобы следующие запросы использовали то же соединение.",
                "The first version opened an ordinary Session. Tests showed that "
                "FastAPI calls dependencies even when parameters are invalid. "
                "Without DATABASE_URL a request with end ≤ start got 503 instead "
                "of 422, and with a database it opened a needless connection. The "
                "fix is <b>LazySession</b>: the engine is chosen at the first SQL "
                "statement and cached. A stable bind makes later statements "
                "reuse the same connection.",
            ),
            BODY_S,
        ),
        Spacer(1, 4),
        code_block(
            "class LazySession(Session):\n"
            "    # __init__: self._resolved_engine = None\n"
            "    def get_bind(self, mapper=None, **kw):\n"
            "        if self._resolved_engine is None:\n"
            "            engine = get_engine()\n"
            "            self._resolved_engine = (\n"
            "                engine.execution_options(\n"
            '                    isolation_level="REPEATABLE READ",\n'
            "                    postgresql_readonly=True,\n"
            "                ) if self.read_only else engine\n"
            "            )\n"
            "        return self._resolved_engine"
        ),
        Spacer(1, 6),
        p(
            tr(
                "<b>Почему def, а не async def.</b> Session и psycopg синхронные; "
                "обычную функцию FastAPI выполняет в пуле потоков, и ожидание базы "
                "не мешает другим запросам. async def с синхронной сессией "
                "заблокировал бы цикл событий всего сервера. Этап 07 применяет "
                "тот же подход к синхронному SDK модели.",
                "<b>Why def and not async def.</b> Session and psycopg are "
                "synchronous; FastAPI runs a plain function in a thread pool, so "
                "waiting for the database does not block other requests. async def "
                "with a synchronous session would block the whole server's event "
                "loop. Stage 07 applies the same approach to the synchronous model SDK.",
            ),
            SMALL,
        ),
        Spacer(1, 6),
        simple_table(
            [tr("Код", "Code"), tr("Когда", "When")],
            [
                [
                    "200 / 201",
                    tr(
                        "Чтение; отчёт сохранён, адрес в заголовке Location.",
                        "A read; a report saved, its address in the Location header.",
                    ),
                ],
                [
                    "404",
                    tr(
                        "Неизвестный путь или UUID отчёта.",
                        "Unknown path or report UUID.",
                    ),
                ],
                [
                    "422",
                    tr(
                        "Неверные параметры или тело; SQL не выполняется.",
                        "Invalid parameters or body; no SQL runs.",
                    ),
                ],
                [
                    "503",
                    tr(
                        "Нет DATABASE_URL, база недоступна или упало соединение.",
                        "No DATABASE_URL, database unreachable or connection lost.",
                    ),
                ],
            ],
            [80, W - 80],
            [CELL, CELL],
        ),
        Spacer(1, 7),
        callout(
            tr(
                '<b>Один текст 503.</b> Клиент получает {"detail": "Database is not '
                'ready"} при любой причине: адрес базы и текст ошибки драйвера '
                "остаются в журнале сервера. Тест подменяет get_engine функцией, "
                "которая падает, и проверяет 422 для 17 неверных запросов: значит, "
                "ни один из них не дошёл до базы.",
                '<b>One 503 text.</b> The client gets {"detail": "Database is not '
                'ready"} for any cause; the database address and driver message stay '
                "in the server log. A test replaces get_engine with a function that "
                "fails and checks 422 for 17 invalid requests, so none of them "
                "reached the database.",
            ),
            VIOLET,
            VIOLET_L,
        ),
    ]

    section(
        story,
        number_of("Сохранённые отчёты"),
        tr(
            "Отчёт — неизменяемый снимок: параметры, результат и версия кода.",
            "A report is an immutable snapshot: parameters, result and code version.",
        ),
        GREEN,
    )
    story += [
        p(
            tr(
                "Миграция <b>0002</b> добавляет таблицу reports. У неё нет внешних "
                "ключей на продажи: отчёт хранит готовый ответ API, а не ссылки "
                "на строки, которые могут измениться.",
                "Migration <b>0002</b> adds the reports table. It has no foreign "
                "keys to sales rows: a report stores a finished API answer, not "
                "links to rows that may change.",
            ),
            BODY_S,
        ),
        Spacer(1, 4),
        simple_table(
            [tr("Столбец", "Column"), tr("Смысл", "Meaning")],
            [
                [
                    mono("id"),
                    tr("UUID, выдаётся при сохранении.", "UUID, set on save."),
                ],
                [
                    mono("kind"),
                    tr(
                        "comparison или anomalies; CHECK в базе.",
                        "comparison or anomalies; a database CHECK.",
                    ),
                ],
                [
                    mono("parameters"),
                    tr("Тело запроса, JSONB.", "The request body as JSONB."),
                ],
                [
                    mono("result"),
                    tr(
                        "Ответ в формате API, JSONB.",
                        "The answer in API format as JSONB.",
                    ),
                ],
                [
                    mono("app_version, created_at"),
                    tr(
                        "Версия кода и время; индекс по created_at.",
                        "Code version and time; an index on created_at.",
                    ),
                ],
            ],
            [160, W - 160],
            [CELL, CELL],
        ),
        Spacer(1, 8),
        code_block(
            "curl -i -X POST http://127.0.0.1:8000/api/reports \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            '  -d \'{"kind": "comparison", "start": "2026-09-01", "end": "2026-10-01",\n'
            '       "compare_start": "2026-08-01", "compare_end": "2026-09-01"}\''
        ),
        Spacer(1, 6),
        p(
            tr(
                "Поле <b>kind</b> — дискриминатор: по нему Pydantic выбирает модель "
                "тела (сравнение с dimension или аномалии с seed). Ответ — 201 и "
                "location: /api/reports/&lt;uuid&gt;. GET по этому адресу отдаёт "
                "тот же JSON; список GET /api/reports идёт от новых к старым, "
                "limit 1–100, без тел result.",
                "The <b>kind</b> field is a discriminator: Pydantic picks the body "
                "model by it (a comparison with dimension or anomalies with seed). "
                "The answer is 201 with location: /api/reports/&lt;uuid&gt;. GET "
                "on that address returns the same JSON; the GET /api/reports list "
                "is newest first, limit 1–100, without result bodies.",
            ),
            BODY_S,
        ),
        p(tr("Снимок, а не ссылка", "A snapshot, not a link"), H2),
        p(
            tr(
                "Тест сохраняет сравнение октября с сентябрём на учебной выборке: "
                "−291 500.00. Затем добавляет октябрьскую продажу на 50 000.00. "
                "Живой маршрут показывает −241 500.00, сохранённый отчёт — "
                "по-прежнему −291 500.00.",
                "A test saves the October vs September comparison on the sample: "
                "−291,500.00. Then it adds a 50,000.00 October sale. The live route "
                "shows −241,500.00 while the saved report still shows −291,500.00.",
            ),
            BODY_S,
        ),
        p(tr("Полный набор через API", "The full dataset through the API"), H2),
        simple_table(
            [
                tr("Запрос к demo, seed 42", "Demo request, seed 42"),
                tr("Результат", "Result"),
                tr("Время, около", "Time, approx."),
            ],
            [
                [
                    tr("Выручка, сентябрь к августу", "Revenue, Sep vs Aug"),
                    tr("−165 497 371.86 (−26.18%)", "−165,497,371.86 (−26.18%)"),
                    tr("30 мс", "30 ms"),
                ],
                [
                    tr("Заказы и средний чек", "Orders and AOV"),
                    tr("1931; 242 542.35 (−24.03%)", "1,931; 242,542.35 (−24.03%)"),
                    tr("16 мс", "16 ms"),
                ],
                [
                    tr("Вклад категорий", "Category contributions"),
                    tr("pumps 83.75%", "pumps 83.75%"),
                    tr("14 мс", "14 ms"),
                ],
                [
                    tr("Аномалии, январь–сентябрь", "Anomalies, Jan–Sep"),
                    tr("33 кандидата", "33 candidates"),
                    tr("177 мс", "177 ms"),
                ],
                [
                    mono("POST /api/reports"),
                    tr("201, GET вернул то же тело", "201, GET returned the same body"),
                    tr("22 мс", "22 ms"),
                ],
            ],
            [175, W - 245, 70],
            [CELL, CELL, CELL],
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Авторизации пока нет.</b> Сервер запускается только на "
                "127.0.0.1. Отчёты нельзя удалить через API, у списка нет общего "
                "числа записей. Доступ по сети — после этапа 09.",
                "<b>There is no authentication yet.</b> Run the server on 127.0.0.1 "
                "only. Reports cannot be deleted through the API and the list has "
                "no total count. Network access comes after Stage 09.",
            ),
            AMBER,
            AMBER_L,
        ),
        Spacer(1, 6),
        callout(
            tr(
                "Проверки: числа API равны функциям ядра, регионы сходятся с "
                "итогом, 422 без SQL, 503 без адреса базы, запись в ReadSession "
                "отклоняется, миграция 0002 откатывается отдельно. Результаты: "
                f"раздел {RESULTS} и docs/VERIFICATION.md. Дальше — AI-агент, этап 07.",
                "Checks: API numbers equal the core functions, regions reconcile "
                "with the total, 422 without SQL, 503 without a database address, "
                "writes in ReadSession are rejected, migration 0002 rolls back "
                f"alone. Results: section {RESULTS} and docs/VERIFICATION.md. "
                "Next is the AI agent in Stage 07.",
            ),
            GREEN,
            GREEN_L,
            SMALL,
        ),
    ]
