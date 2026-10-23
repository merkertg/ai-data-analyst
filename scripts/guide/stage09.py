"""Bilingual sections 40–42: access tokens, limits and attacks, agent evals."""

from reportlab.platypus import Spacer

from guide.diagrams import auth_flow, eval_flow
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
    ORANGE,
    ORANGE_L,
    SMALL,
    VIOLET,
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


def add_stage09(story):
    """Explain access control, attack tests and the independent eval oracle."""
    section(
        story,
        number_of("Доступ по токенам"),
        tr(
            "Каждый маршрут /api требует токен; в базе хранится только его SHA-256.",
            "Every /api route needs a token; the database keeps only its SHA-256.",
        ),
        BLUE,
    )
    story += [
        p(
            tr(
                "До этапа 09 API был открыт любому, кто достучится до порта. "
                "Теперь запрос к /api проходит четыре проверки до маршрута. "
                "Открыты только /health, /ready и документация: в них нет "
                "данных о продажах.",
                "Before Stage 09 the API was open to anyone who could reach the "
                "port. Now a request to /api passes four checks before the route. "
                "Only /health, /ready and the documentation stay open: they hold "
                "no sales data.",
            )
        ),
        Diagram(96, auth_flow),
        Spacer(1, 6),
        simple_table(
            [tr("Роль", "Role"), tr("Может", "Allowed")],
            [
                [
                    "viewer",
                    tr(
                        "Читать показатели, аналитику, отчёты и историю агента.",
                        "Read metrics, analytics, reports and agent history.",
                    ),
                ],
                [
                    "analyst",
                    tr(
                        "То же, а ещё сохранять отчёты и спрашивать агента.",
                        "The same, plus saving reports and asking the agent.",
                    ),
                ],
            ],
            [90, W - 90],
            [CELL, CELL],
        ),
        Spacer(1, 6),
        code_block(
            'uv run python -m app.security issue --name "Streamlit" --role analyst --days 90\n'
            "uv run python -m app.security list\n"
            "uv run python -m app.security revoke <id>"
        ),
        Spacer(1, 6),
        p(
            tr(
                "Токен — ida_ и 32 случайных байта; он показывается один раз. "
                "В таблице api_tokens (миграция 0004) лежат SHA-256 и первые 12 "
                "символов. 256 случайных бит не перебрать, поэтому быстрого хэша "
                "достаточно: медленный нужен коротким паролям людей. Отсутствующий, "
                "чужой, отозванный и просроченный токен получают один и тот же 401; "
                "токен неверного формата отклоняется до SQL. HTTP-маршрута для "
                "выдачи токенов нет: украденный токен не выпустит новый.",
                "A token is ida_ plus 32 random bytes and is shown once. Table "
                "api_tokens (migration 0004) keeps its SHA-256 and first 12 "
                "characters. 256 random bits cannot be guessed, so a fast hash is "
                "enough; slow hashing is for short human passwords. Missing, "
                "unknown, revoked and expired tokens get the same 401; a malformed "
                "token is rejected before SQL. There is no HTTP route for issuing "
                "tokens, so a stolen token cannot create new ones.",
            ),
            BODY_S,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Лимиты на токен.</b> 6 запусков агента и 30 сохранений отчёта "
                "в минуту, скользящее окно; сверх — 429 с Retry-After. Вживую: "
                "шесть запусков — 201, седьмой — 429, Retry-After: 59. Счётчики "
                "живут в памяти одного процесса. Интерфейс берёт токен из "
                "UI_API_TOKEN и объясняет 401, 403 и 429.",
                "<b>Per-token limits.</b> 6 agent runs and 30 report saves per "
                "minute, sliding window; beyond that a 429 with Retry-After. Live: "
                "six runs gave 201, the seventh 429, Retry-After: 59. Counters "
                "live in one process's memory. The UI reads the token from "
                "UI_API_TOKEN and explains 401, 403 and 429.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    section(
        story,
        number_of("Ограничения и атаки"),
        tr(
            "Тесты нападают на API и агента; данные при этом не меняются.",
            "Tests attack the API and the agent; the data never changes.",
        ),
        ORANGE,
    )
    story += [
        simple_table(
            [tr("Защита", "Control"), tr("Как работает", "How it works")],
            [
                [
                    tr("Нет свободного SQL", "No free-form SQL"),
                    tr(
                        "Модель выбирает из девяти функций; запросы написаны заранее.",
                        "The model picks one of nine functions; queries are pre-written.",
                    ),
                ],
                [
                    tr("Параметры", "Bound values"),
                    tr(
                        "'x'; DROP TABLE orders; --' — просто несуществующая категория.",
                        "'x'; DROP TABLE orders; --' is just a missing category.",
                    ),
                ],
                [
                    "READ ONLY",
                    tr(
                        "Инструменты и GET: запись отклоняет сама PostgreSQL.",
                        "Tools and GETs: PostgreSQL itself rejects writes.",
                    ),
                ],
                [
                    mono("statement_timeout"),
                    tr(
                        "15 000 мс на любой запрос; pg_sleep(2) при 200 мс → QueryCanceled.",
                        "15,000 ms per statement; pg_sleep(2) at 200 ms → QueryCanceled.",
                    ),
                ],
                [
                    tr("Эталон закрыт", "Answer key closed"),
                    tr(
                        "Ни один модуль агента, API и UI не знает ground_truth.",
                        "No agent, API or UI module mentions ground_truth.",
                    ),
                ],
            ],
            [140, W - 140],
            [CELL, CELL],
        ),
        p(tr("Враждебная модель", "A hostile model"), H2),
        p(
            tr(
                "Сценарный провайдер играет взломанную модель: просит drop_table "
                "и run_sql, прячет DELETE в аргументы, ставит limit 100000, "
                "передаёт путь к ground_truth.json вместо категории и пишет «выручка "
                "выросла на 50%». Все вызовы получают ошибку, «путь» — просто "
                "несуществующая категория, отчёт отклонён дважды, запуск сохранён "
                "с ошибкой unverified_report (502). Строки в таблицах продаж не "
                "изменились.",
                "A scripted provider plays a compromised model: it asks for "
                "drop_table and run_sql, hides DELETE in arguments, sets limit "
                "100000, passes a path to ground_truth.json as a category and "
                "writes “revenue grew 50%”. Every call gets an error, the “path” "
                "is just a missing category, the report is rejected twice and the "
                "run is stored as unverified_report (502). Sales rows are unchanged.",
            ),
            BODY_S,
        ),
        Spacer(1, 4),
        simple_table(
            [tr("Атака", "Attack"), tr("Итог", "Outcome")],
            [
                [
                    tr(
                        "Нет токена, чужая схема, мусор, неизвестный",
                        "No token, wrong scheme, junk, unknown",
                    ),
                    tr("Один и тот же 401", "The same 401"),
                ],
                [
                    tr("Отозванный или просроченный токен", "Revoked or expired token"),
                    tr("401 со следующего запроса", "401 from the next request"),
                ],
                [
                    tr(
                        "viewer сохраняет отчёт или спрашивает агента",
                        "viewer saves a report or asks the agent",
                    ),
                    "403",
                ],
                [
                    tr(
                        "Каждый путь /api из OpenAPI без токена",
                        "Every /api path in OpenAPI without a token",
                    ),
                    "401",
                ],
                [
                    tr("6 инъекций × 3 инструмента", "6 injections × 3 tools"),
                    tr(
                        "Пустой результат, строки не изменились",
                        "Empty result, rows unchanged",
                    ),
                ],
                [
                    tr(
                        "Число 999 в названии категории",
                        "The number 999 inside a category name",
                    ),
                    tr(
                        "Отклонено проверкой доказательств",
                        "Rejected by the evidence check",
                    ),
                ],
                [
                    tr("Ключ OpenAI в тексте ошибки SDK", "OpenAI key in an SDK error"),
                    tr(
                        "Нет ни в ответе, ни в базе",
                        "Absent from the answer and the database",
                    ),
                ],
            ],
            [260, W - 260],
            [CELL, CELL],
        ),
        Spacer(1, 7),
        callout(
            tr(
                "55 тестов tests/security/ проходят. Обычные тесты API «входят» "
                "тестовым аналитиком (общая фикстура), а тесты с маркером real_auth "
                "выпускают настоящие токены в базе *_test.",
                "All 55 tests in tests/security/ pass. Ordinary API tests sign in "
                "as a test analyst (a shared fixture); tests marked real_auth issue "
                "real tokens in the *_test database.",
            ),
            ORANGE,
            ORANGE_L,
        ),
    ]

    section(
        story,
        number_of("Evals агента"),
        tr(
            "42 вопроса; правильные ответы считает Pandas прямо из CSV, без SQL.",
            "42 questions; Pandas computes the right answers from CSV, without SQL.",
        ),
        VIOLET,
    )
    story += [
        Diagram(132, eval_flow),
        Spacer(1, 6),
        p(
            tr(
                "Вопросы: 8 показателей, 6 сравнений, 8 вкладов групп, 5 о возвратах, "
                "4 о товарах, 4 об остатках, 3 без данных, 3 запрещённых и 1 "
                "инъекция; 27 на русском, 15 на английском. В файле нет ожидаемых "
                "чисел: эталон считает независимо от SQL. Без заказов средний чек "
                "и его изменение — null; процент при нулевой базе — тоже null, "
                "а не ноль или строка None.",
                "Questions: 8 metrics, 6 comparisons, 8 group contributions, "
                "5 refunds, 4 products, 4 stock, 3 without data, 3 forbidden and "
                "1 injection; 27 in Russian, 15 in English. The file holds no "
                "expected numbers: the oracle computes independently of SQL. "
                "Without paid orders, AOV and its change are null; a percentage "
                "with a zero base is null, never zero or the string None.",
            ),
            BODY_S,
        ),
        Spacer(1, 4),
        code_block(
            "# quantity × price × (1 − discount), half up, in whole kopecks\n"
            'items["amount"] = (items["quantity"] * price * (10000 - discount) + 5000) // 10000'
        ),
        Spacer(1, 6),
        simple_table(
            [
                tr("Провайдер", "Provider"),
                tr("Пройдено", "Passed"),
                tr("Значения", "Values"),
                tr("Отказы", "Refusals"),
            ],
            [
                [
                    tr("reference — записанные вызовы", "reference — recorded calls"),
                    "42 / 42",
                    "1.00",
                    "3 / 3",
                ],
                [
                    tr("mock — ключевые слова", "mock — keywords"),
                    "17 / 42",
                    "0.47",
                    "0 / 3",
                ],
                [tr("OpenAI", "OpenAI"), tr("не измерен", "not measured"), "—", "—"],
            ],
            [200, 90, 90, W - 380],
            [CELL, CELL, CELL, CELL],
        ),
        Spacer(1, 6),
        p(
            tr(
                "История 22 октября: SQL и Pandas совпали до копейки на 42 вопросах. "
                "Выбор инструментов: только 38 вопросов с tools_any; 4 без "
                "инструмента исключены, неудачный запуск — промах. Reference: "
                "38/38, mock: 34/38 = 0.8947; пройдено по-прежнему 42/42 и 17/42. "
                "Нет подходящих вопросов — метрика null. Модель мерит --provider openai.",
                "Historical, 22 October: SQL and Pandas agree to the kopeck on 42 questions. "
                "Tool selection covers only 38 cases with tools_any; 4 requiring "
                "no tool are excluded and failed runs are misses. Reference: "
                "38/38, mock: 34/38 = 0.8947; passes remain 42/42 and 17/42. "
                "No applicable cases means a null rate. --provider openai measures a model.",
            ),
            BODY_S,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>До вопросов:</b> manifest, хэши и CSV проверены; каждое поле "
                "всех 6 таблиц, включая остатки, сверено по id в одном READ ONLY "
                "снимке, SQL читается порциями по 1000 строк. Decimal и время "
                "сравниваются по значению. Одних чисел строк недостаточно. "
                "Не меняй набор во время eval: инструменты открывают свои снимки.",
                "<b>Before questions:</b> verify the manifest, hashes and CSVs; "
                "compare every field of all 6 tables, including stock, by id in "
                "one READ ONLY snapshot, streaming SQL in batches of 1000. "
                "Decimal and timestamp values must match. Counts alone are "
                "insufficient. Keep data unchanged: tools use separate snapshots.",
            ),
            AMBER,
            AMBER_L,
        ),
        Spacer(1, 6),
        callout(
            tr(
                "При завершении этапа 09: 578 тестов, из них 55 безопасности и "
                "27 evals; оба провайдера включены в CI на seed 42. Текущие "
                f"проверки: раздел {RESULTS}; методика — docs/EVALUATION.md, "
                "защита — docs/SECURITY.md.",
                "At Stage 09 completion: 578 tests, including 55 security and "
                "27 eval tests; both providers are included in CI on seed 42. "
                f"Current checks: section {RESULTS}; method: docs/EVALUATION.md; "
                "security: docs/SECURITY.md.",
            ),
            GREEN,
            GREEN_L,
            SMALL,
        ),
    ]
