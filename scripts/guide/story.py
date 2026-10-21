"""Assemble the overview, Stages 01–08, CI, reference pages and results."""

from html import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import KeepTogether, NextPageTemplate, PageBreak, Spacer

from guide.diagrams import STAGES_DONE, ci_pipeline, roadmap
from guide.i18n import language, loc, tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BLUE,
    BLUE_L,
    BODY_S,
    CELL,
    GREEN,
    GREEN_L,
    H2,
    ORANGE,
    ORANGE_L,
    QUESTION,
    SMALL,
    TEAL,
    TEAL_L,
    VIOLET,
    VIOLET_L,
    Diagram,
    W,
    callout,
    cards,
    grid_table,
    mono,
    p,
    simple_table,
)
from guide.stage01 import add_stage01
from guide.stage02 import add_stage02
from guide.stage03 import add_stage03
from guide.stage04 import add_stage04
from guide.stage05 import add_stage05
from guide.stage06 import add_stage06
from guide.stage07 import add_stage07
from guide.stage08 import add_stage08
from guide.toc import number_of, section

# Плотные ячейки для таблиц итогов: страница итогов помещается целиком.
CELL_TIGHT = ParagraphStyle("celltight", parent=CELL, fontSize=8.3, leading=10.4)
HEAD_TIGHT = ParagraphStyle(
    "headtight", parent=CELL_TIGHT, fontName="PT-Bold", textColor="#FFFFFF"
)
TIGHT_PADDING = [
    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
]


def tight_table(headers, rows, widths):
    """Таблица с уменьшенным шрифтом и отступами для страницы итогов."""
    prepared = [[p(value, HEAD_TIGHT) for value in headers]]
    prepared += [[p(value, CELL_TIGHT) for value in row] for row in rows]
    return grid_table(prepared, widths, styles=TIGHT_PADDING)


# Как статус удалённого CI из verification.json звучит в тексте.
REMOTE_LABELS = {
    "not_verified": ("не подтверждён", "not confirmed"),
    "passed": ("задание зелёное", "the job is green"),
    "failed": ("задание упало", "the job failed"),
}


def remote_label(status: str) -> str:
    """Статус удалённого CI на текущем языке."""
    return tr(*REMOTE_LABELS[status])


def build_story(verification, dependencies, lock_packages, facts, counts):
    """Assemble all guide pages after the cover from bilingual sources."""
    story = [NextPageTemplate("content"), PageBreak()]
    tests = verification["tests"]

    # 1. Проект за минуту
    section(
        story,
        1,
        tr(
            "Что уже работает, чего ещё нет и где проект в плане курса.",
            "What already works, what does not exist yet and where the project is in "
            "the course plan.",
        ),
    )
    story += [
        p(
            tr(
                "<b>AI Data Analyst</b> — ИИ-аналитик вымышленной компании "
                "<b>IndustrialFlow</b>, которая продаёт насосы, компрессоры, арматуру и "
                "датчики. Руководитель задаёт вопрос обычным языком, а агент вызывает "
                "аналитические инструменты, точно считает показатели и пишет отчёт. "
                f"Готовы этапы 01–{STAGES_DONE:02d}: каркас API с проверками и CI, "
                "база PostgreSQL, данные, проверки качества, точная аналитика, "
                "поиск аномалий, REST\u00a0API и AI-агент с инструментами, "
                "проверкой доказательств и историей запусков; интерфейс Streamlit "
                "с показателями, графиками и сохранёнными отчётами.",
                "<b>AI Data Analyst</b> is an AI analyst for <b>IndustrialFlow</b>, a "
                "fictional company selling pumps, compressors, valves and sensors. A "
                "manager asks in plain language; the agent calls analytics tools, "
                "computes exact metrics and writes a report. "
                f"Stages 01–{STAGES_DONE:02d} are done: an API foundation with checks "
                "and CI, a PostgreSQL database, reproducible data, quality checks, "
                "exact analytics, anomaly detection, a REST API and an AI agent "
                "with tools, evidence checks and run history; a Streamlit interface "
                "with metrics, charts and saved reports.",
            )
        ),
        Spacer(1, 10),
        cards(
            [
                (
                    "API",
                    tr(
                        "FastAPI: /health и /ready; метрики, вклады групп и аномалии "
                        "по /api/...; отчёты и запуски агента. /docs строится сама.",
                        "FastAPI: /health and /ready; metrics, group contributions and "
                        "anomalies under /api/...; reports and agent runs. /docs is generated.",
                    ),
                    BLUE,
                    BLUE_L,
                ),
                (
                    tr("База данных", "Database"),
                    tr(
                        "PostgreSQL 17 в Docker Compose: 6 таблиц данных, 28 правил "
                        "целостности, NUMERIC и timestamptz; отдельно reports и agent_runs.",
                        "PostgreSQL 17 in Docker Compose: 6 data tables, 28 integrity "
                        "rules, NUMERIC and timestamptz; reports and agent_runs are separate.",
                    ),
                    TEAL,
                    TEAL_L,
                ),
                (
                    tr("Миграции", "Migrations"),
                    tr(
                        "Схема создаётся и откатывается только Alembic; alembic check ловит "
                        "модель без миграции.",
                        "The schema is created and rolled back only by Alembic; alembic "
                        "check catches a model without a migration.",
                    ),
                    VIOLET,
                    VIOLET_L,
                ),
                (
                    tr("Тесты", "Tests"),
                    tr(
                        f"{tests['total']} тестов pytest: {tests['unit']} unit и "
                        f"{tests['integration']} на настоящей PostgreSQL. Все проходят.",
                        f"{tests['total']} pytest tests: {tests['unit']} unit and "
                        f"{tests['integration']} on a real PostgreSQL. All pass.",
                    ),
                    GREEN,
                    GREEN_L,
                ),
                (
                    tr("Качество", "Quality"),
                    tr(
                        "Ruff проверяет стиль и форматирует код и примеры в Markdown; mypy в "
                        "строгом режиме проверяет типы.",
                        "Ruff checks style and formats code and Markdown examples; mypy "
                        "checks types in strict mode.",
                    ),
                    ORANGE,
                    ORANGE_L,
                ),
                (
                    "CI",
                    tr(
                        "GitHub Actions повторяет всё на чистой Linux-машине с отдельной "
                        "PostgreSQL при каждом push и pull request.",
                        "GitHub Actions repeats everything on a clean Linux machine with its "
                        "own PostgreSQL on every push and pull request.",
                    ),
                    AMBER,
                    AMBER_L,
                ),
            ]
        ),
        p(tr("Где мы в плане курса", "Where we are in the course plan"), H2),
        Diagram(114, roadmap),
        Spacer(1, 12),
        callout(
            tr(
                "<b>Числа считает код, а не LLM.</b> Выручку, средний чек, сравнения и "
                "аномалии рассчитывает детерминированный SQL или Python. Модель "
                "понимает вопрос, выбирает инструменты и объясняет результат. Поэтому "
                "так важны правила в базе, точные типы денег и тесты.",
                "<b>Numbers come from code, not from the LLM.</b> Revenue, average order "
                "value, comparisons and anomalies are computed by deterministic SQL or "
                "Python. The model understands the question, picks tools and explains "
                "the result. That is why database rules, exact money types and tests "
                "matter.",
            ),
        ),
        Spacer(1, 8),
        callout(
            tr(
                "<b>Границы проверки:</b> агент проверен с mock и поддельным SDK, "
                "живой вызов OpenAI ещё не проверен. Интерфейс Streamlit работает "
                "с тем же API; авторизация (09) и публикация (10) ещё впереди.",
                "<b>Verification limits:</b> the agent was tested with mock and "
                "a fake SDK; a live OpenAI call is still untested. The Streamlit UI "
                "uses the same API; authentication (09) and release (10) come later.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    if language() == "en":
        # Source excerpts preserve the language and names used by the project.
        story += [
            Spacer(1, 8),
            p(
                "Code excerpts are shown exactly as they are in the repository, so "
                "comments may be in Russian or English. The small sample uses "
                "Russian names; generated demo data uses English labels. Detailed stage guides "
                "are in Russian (docs/STAGE_*.md); short task instructions are in "
                "English (docs/instructions/).",
                SMALL,
            ),
        ]

    add_stage01(story, verification, dependencies, lock_packages, facts)
    add_stage02(story, verification, counts)
    add_stage03(story)
    add_stage04(story)
    add_stage05(story)
    add_stage06(story)
    add_stage07(story)
    add_stage08(story)

    # CI on GitHub Actions
    remote = verification["remote_ci"]
    section(
        story,
        number_of("CI на GitHub Actions"),
        tr(
            "Те же проверки на чистой Linux-машине с отдельной PostgreSQL.",
            "The same checks on a clean Linux machine with its own PostgreSQL.",
        ),
        ORANGE,
    )
    story += [
        Diagram(236, ci_pipeline),
        Spacer(1, 12),
        simple_table(
            [tr("Настройка", "Setting"), tr("Зачем", "Why")],
            [
                [
                    mono("services: postgres"),
                    tr(
                        "Отдельная база industrialflow_test на время запуска; образ по digest, как в compose.yaml.",
                        "A dedicated industrialflow_test database for the run; image pinned by digest as in compose.yaml.",
                    ),
                ],
                [
                    mono("DATABASE_URL, TEST_DATABASE_URL"),
                    tr(
                        "Alembic и тесты работают с одной базой *_test.",
                        "Alembic and tests use the same *_test database.",
                    ),
                ],
                [
                    mono("CI=true"),
                    tr(
                        "Интеграционные тесты без адреса падают, а не пропускаются.",
                        "Integration tests without an address fail instead of being skipped.",
                    ),
                ],
                [
                    mono("permissions: contents: read"),
                    tr(
                        "Заданию разрешено только читать код.",
                        "The job may only read the code.",
                    ),
                ],
                [
                    mono("checkout@3d3c42e… # v7.0.1"),
                    tr(
                        "Действия закреплены полным SHA: тег можно перенести, SHA — нет.",
                        "Actions are pinned by full SHA: a tag can move, a SHA cannot.",
                    ),
                ],
                [
                    mono("concurrency"),
                    tr(
                        "Новый push в тот же PR отменяет устаревшую проверку.",
                        "A new push to the same PR cancels the outdated run.",
                    ),
                ],
            ],
            [200, W - 200],
            [CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            tr(
                f"<b>Статус удалённого CI: {remote_label(remote['status'])}.</b> ",
                f"<b>Remote CI status: {remote_label(remote['status'])}.</b> ",
            )
            + escape(loc(remote["detail"])),
            AMBER,
            AMBER_L,
        ),
    ]

    # Command cheat sheet
    section(
        story,
        number_of("Шпаргалка команд"),
        tr(
            f"Основные команды этапов 01–{STAGES_DONE:02d}.",
            f"Essential commands for Stages 01–{STAGES_DONE:02d}.",
        ),
        TEAL,
    )
    commands = [
        (
            tr("Создать окружение по lock", "Create the environment from the lock"),
            "uv sync --locked",
        ),
        (
            tr("Запустить PostgreSQL", "Start PostgreSQL"),
            "docker compose up --detach --wait db",
        ),
        (tr("Применить миграции", "Apply migrations"), "uv run alembic upgrade head"),
        (
            tr("Создать demo", "Generate demo"),
            "uv run python -m app.data.generate --output data/demo",
        ),
        (
            tr("Загрузить demo", "Load demo"),
            "uv run python -m app.data.load --input data/demo",
        ),
        (
            tr("Качество данных", "Data quality"),
            "uv run python -m app.data.quality",
        ),
        (
            tr("Показатели сентября", "September metrics"),
            "uv run python -m app.analytics --start 2026-09-01 --end 2026-10-01",
        ),
        (
            tr("Кандидаты на аномалии", "Anomaly candidates"),
            "uv run python -m app.analytics.anomalies --start 2026-01-01 --end 2026-10-01",
        ),
        (
            tr("Запустить сервер", "Start the server"),
            "uv run uvicorn app.main:app --reload",
        ),
        (
            tr("Проверить готовность", "Check readiness"),
            "curl -i http://127.0.0.1:8000/ready",
        ),
        (
            tr("Запустить интерфейс", "Start the interface"),
            "uv run python -m streamlit run ui/main.py --server.address 127.0.0.1",
        ),
        (
            tr("Выручка через API", "Revenue via the API"),
            "curl '127.0.0.1:8000/api/metrics/revenue?start=2026-09-01&end=2026-10-01'",
        ),
        (
            tr("Сохранённые отчёты", "Saved reports"),
            "curl '127.0.0.1:8000/api/reports?limit=10'",
        ),
        (
            tr("История агента", "Agent history"),
            "curl '127.0.0.1:8000/api/agent/runs?limit=10'",
        ),
        (
            tr("Тестовая база", "Test database"),
            "docker compose --profile test up --detach --wait db-test",
        ),
        (tr("Все тесты", "All tests"), "TEST_DATABASE_URL=... uv run pytest"),
        (
            tr("Только интеграционные", "Integration only"),
            "uv run pytest -m integration",
        ),
        (
            tr("Линтер и формат", "Lint and format"),
            "uv run ruff check . && uv run ruff format --check .",
        ),
        (tr("Типы", "Types"), "uv run mypy app ui tests migrations"),
        (
            tr("Оценка сценариев", "Scenario evaluation"),
            "uv run python -m app.analytics.evaluate --help",
        ),
        (tr("Модели = миграции?", "Models = migrations?"), "uv run alembic check"),
        (
            tr("Откатить одну миграцию", "Roll back one migration"),
            "uv run alembic downgrade -1",
        ),
        (tr("Версия схемы", "Schema version"), "uv run alembic current"),
        (tr("Остановить базу", "Stop the database"), "docker compose stop"),
        (tr("Проверить lock", "Check the lock"), "uv lock --check"),
        (
            tr("Пересобрать PDF", "Rebuild the PDF"),
            "uv run --with 'reportlab==4.4.9' python scripts/build_guide.py",
        ),
    ]
    story.append(
        simple_table(
            [tr("Задача", "Task"), tr("Команда", "Command")],
            [[task, mono(command)] for task, command in commands],
            [165, W - 165],
        )
    )

    # Common errors
    section(
        story,
        number_of("Типичные ошибки"),
        tr("Симптом, причина и что сделать.", "Symptom, cause and fix."),
        ORANGE,
    )
    errors = [
        (
            mono("uv: command not found"),
            tr(
                "Терминал открыт до установки uv",
                "Terminal opened before installing uv",
            ),
            tr("Новая вкладка Terminal", "Open a new terminal tab"),
        ),
        (
            mono("No module named 'app'"),
            tr(
                "Нет pythonpath или команда не из корня",
                "No pythonpath or not run from the root",
            ),
            tr(
                "Проверить pyproject.toml, cd в корень",
                "Check pyproject.toml, cd to the root",
            ),
        ),
        (
            mono("Address already in use"),
            tr("Порт занят", "Port is busy"),
            mono("lsof -i :8000") + ", " + mono("--port 8001"),
        ),
        (
            mono("405 Method Not Allowed"),
            tr("Не тот HTTP-метод", "Wrong HTTP method"),
            tr("Для /health — GET", "Use GET for /health"),
        ),
        (
            mono("uv sync --locked") + tr(" падает", " fails"),
            tr("pyproject изменён, lock — нет", "pyproject changed, lock did not"),
            mono("uv lock") + tr(" и коммит uv.lock", " and commit uv.lock"),
        ),
        (
            tr("Изменения .env не видны", ".env changes ignored"),
            tr("Настройки читаются при старте", "Settings are read at startup"),
            tr("Перезапустить сервер", "Restart the server"),
        ),
        (
            mono("failed to connect to the docker API"),
            tr("Docker Desktop не запущен", "Docker Desktop is not running"),
            tr("Запустить Docker Desktop", "Start Docker Desktop"),
        ),
        (
            mono("POSTGRES_PASSWORD is missing"),
            tr("Нет .env", "No .env"),
            mono("cp .env.example .env"),
        ),
        (
            mono("port is already allocated"),
            tr("Порт 5436 занят", "Port 5436 is busy"),
            tr(
                "Сменить POSTGRES_PORT и DATABASE_URL",
                "Change POSTGRES_PORT and DATABASE_URL",
            ),
        ),
        (
            mono("DATABASE_URL не задан"),
            tr("Нет .env или переменной", "No .env or variable"),
            tr("Создать .env", "Create .env"),
        ),
        (
            tr("/ready → 503 при живой базе", "/ready → 503 with a live database"),
            tr("Миграции не применены", "Migrations not applied"),
            mono("uv run alembic upgrade head"),
        ),
        (
            mono("New upgrade operations detected"),
            tr("Модель изменена без миграции", "Model changed without a migration"),
            tr("Новая миграция --autogenerate", "A new --autogenerate migration"),
        ),
        (
            tr("Интеграционные тесты skipped", "Integration tests skipped"),
            tr("Нет TEST_DATABASE_URL", "No TEST_DATABASE_URL"),
            tr(
                "Запустить db-test, задать переменную",
                "Start db-test, set the variable",
            ),
        ),
        (
            tr(
                "«только для базы с суффиксом _test»",
                "“only for a database ending with _test”",
            ),
            tr(
                "Адрес указывает на другую базу",
                "The address points to another database",
            ),
            tr("Указать базу *_test", "Use a *_test database"),
        ),
        (
            mono("IntegrityError"),
            tr("Нарушено правило целостности", "An integrity rule is violated"),
            tr(
                "Имя ограничения в тексте ошибки",
                "Read the constraint name in the error",
            ),
        ),
        (
            tr("API отвечает 422", "The API answers 422"),
            tr(
                "Лишний параметр, end ≤ start, > 120 мес.",
                "Extra parameter, end ≤ start, > 120 months",
            ),
            tr("Прочитать detail[].loc и msg", "Read detail[].loc and msg"),
        ),
        (
            tr("API отвечает 503 на всё", "The API answers 503 to everything"),
            tr("База не запущена или нет DATABASE_URL", "No database or DATABASE_URL"),
            tr("Запустить db, проверить /ready", "Start db, check /ready"),
        ),
        (
            tr("Данные пропали", "Data is gone"),
            mono("docker compose down -v"),
            tr("Без -v том сохраняется", "Without -v the volume stays"),
        ),
    ]
    story.append(
        simple_table(
            [
                tr("Симптом", "Symptom"),
                tr("Причина", "Cause"),
                tr("Что сделать", "Fix"),
            ],
            [list(row) for row in errors],
            [185, 150, W - 335],
            [CELL, CELL, CELL],
        )
    )

    # Check yourself
    section(
        story,
        number_of("Проверь себя"),
        tr(
            "Вопросы для самопроверки и самостоятельные задания.",
            "Self-check questions and practice tasks.",
        ),
        VIOLET,
    )
    questions = [
        (
            tr(
                "Чем pyproject.toml отличается от uv.lock?",
                "How does pyproject.toml differ from uv.lock?",
            ),
            tr(
                "pyproject — требования к прямым зависимостям, uv.lock — точные версии и хэши всех пакетов.",
                "pyproject holds requirements for direct dependencies; uv.lock holds exact versions and hashes of all packages.",
            ),
        ),
        (
            tr(
                "Почему Uvicorn находит app, а pytest без настройки — нет?",
                "Why does Uvicorn find app while pytest without a setting does not?",
            ),
            tr(
                'Uvicorn добавляет текущую папку в sys.path, pytest — папку tests/. pythonpath = ["."] добавляет корень.',
                'Uvicorn adds the current folder to sys.path, pytest adds tests/. pythonpath = ["."] adds the root.',
            ),
        ),
        (
            tr(
                'Что будет, если health() вернёт {"status": "fail"}?',
                'What happens if health() returns {"status": "fail"}?',
            ),
            tr(
                "mypy найдёт ошибку до запуска; при запросе FastAPI выбросит ResponseValidationError, клиент получит 500.",
                "mypy finds it before running; on a request FastAPI raises ResponseValidationError and the client gets 500.",
            ),
        ),
        (
            tr(
                "Почему заказ хранится в двух таблицах?",
                "Why is an order stored in two tables?",
            ),
            tr(
                "Один заказ — много товаров; нормализация хранит свойства заказа один раз, а товары — построчно.",
                "One order holds many products; normalisation stores order properties once and products line by line.",
            ),
        ),
        (
            tr(
                "Чем CASCADE отличается от RESTRICT?",
                "How does CASCADE differ from RESTRICT?",
            ),
            tr(
                "CASCADE удаляет зависимые строки вместе с родителем; RESTRICT запрещает удалить родителя со ссылками.",
                "CASCADE deletes dependent rows with the parent; RESTRICT forbids deleting a referenced parent.",
            ),
        ),
        (
            tr(
                "Почему деньги — NUMERIC и Decimal?",
                "Why is money NUMERIC and Decimal?",
            ),
            tr(
                "float двоичный и не хранит 0.1 точно; NUMERIC и Decimal хранят десятичные числа точно.",
                "float is binary and cannot store 0.1 exactly; NUMERIC and Decimal store decimals exactly.",
            ),
        ),
        (
            tr(
                "Зачем AT TIME ZONE 'Europe/Moscow'?",
                "Why AT TIME ZONE 'Europe/Moscow'?",
            ),
            tr(
                "Отчётный месяц московский: оплата 1 октября в 01:30 МСК по UTC попала бы в сентябрь.",
                "Reporting months are Moscow time: a payment at 01:30 MSK on 1 October would fall into September in UTC.",
            ),
        ),
        (
            tr(
                "Почему применённую миграцию не редактируют?",
                "Why is an applied migration never edited?",
            ),
            tr(
                "Иначе разные базы окажутся с одинаковым номером версии; изменение — новая миграция.",
                "Different databases would share a version number; a change is a new migration.",
            ),
        ),
        (
            tr(
                "Почему JOIN с возвратами завышает продажи?",
                "Why does a JOIN with refunds inflate sales?",
            ),
            tr(
                "Позиция повторяется на каждый возврат; нужно сначала свести таблицу «многих» к строке на ключ.",
                "The line repeats once per refund; reduce the “many” table to one row per key first.",
            ),
        ),
        (
            tr(
                "Чем /ready отличается от /health?",
                "How does /ready differ from /health?",
            ),
            tr(
                "/health — процесс жив, база не нужна; /ready — база доступна и схема актуальна, иначе 503.",
                "/health — the process is alive, no database needed; /ready — database reachable and current, otherwise 503.",
            ),
        ),
        (
            tr(
                "Почему неверный запрос получает 422, даже когда база выключена?",
                "Why does an invalid request get 422 even when the database is down?",
            ),
            tr(
                "Параметры проверяет Pydantic до маршрута, а LazySession выбирает engine только при первом SQL.",
                "Pydantic validates parameters before the route, and LazySession picks the engine only at the first SQL statement.",
            ),
        ),
        (
            tr(
                "Почему сохранённый отчёт не меняется после новых продаж?",
                "Why does a saved report not change after new sales?",
            ),
            tr(
                "Результат считается один раз и хранится в JSONB; GET отдаёт снимок, а не пересчёт.",
                "The result is computed once and stored as JSONB; GET returns the snapshot, not a recalculation.",
            ),
        ),
    ]
    for index, (question, answer) in enumerate(questions, start=1):
        story += [
            p(f"{index}. {escape(question)}", QUESTION),
            p(tr("Ответ: ", "Answer: ") + escape(answer), SMALL),
            Spacer(1, 4),
        ]
    story += [
        p(tr("Самостоятельные задания", "Practice tasks"), H2),
        callout(
            tr(
                "<b>Этап 01.</b> Маршрут GET /version с моделью VersionResponse: name — из "
                "get_settings().app_name, version — из app.__version__; тест на 200 и тело ответа.",
                "<b>Stage 01.</b> A GET /version route with a VersionResponse model: name "
                "from get_settings().app_name, version from app.__version__; a test for 200 "
                "and the body.",
            ),
            VIOLET,
            VIOLET_L,
        ),
        Spacer(1, 6),
        callout(
            tr(
                "<b>Этап 02.</b> Столбец products.is_active (boolean, NOT NULL, по умолчанию "
                "true) новой миграцией 0004 с server_default; alembic check молчит, откат "
                "downgrade -1 работает, есть тест.",
                "<b>Stage 02.</b> A products.is_active column (boolean, NOT NULL, default "
                "true) via a new migration 0004 with server_default; alembic check is quiet, "
                "downgrade -1 works, a test exists.",
            ),
            TEAL,
            TEAL_L,
        ),
        Spacer(1, 6),
        callout(
            tr(
                "<b>Этап 06.</b> Маршрут DELETE /api/reports/{report_id}: 204 после "
                "удаления, 404 для неизвестного UUID; тест, что следующий GET даёт 404, "
                "а GET-маршруты по-прежнему не могут писать.",
                "<b>Stage 06.</b> A DELETE /api/reports/{report_id} route: 204 after "
                "deletion, 404 for an unknown UUID; a test that the next GET is 404 "
                "and GET routes still cannot write.",
            ),
            BLUE,
            BLUE_L,
        ),
    ]

    # Verification results
    environment = verification["environment"]
    section(
        story,
        number_of("Итоги проверки"),
        tr(
            f"Дата проверки: {verification['checked_at']}; база рабочего дерева "
            f"{verification['base_commit']}.",
            f"Verified on {verification['checked_at']}; working-tree base "
            f"{verification['base_commit']}.",
        ),
        GREEN,
    )
    story += [
        p(
            tr(
                f"Окружение: {loc(environment['os'])}, uv {environment['uv']}, Python "
                f"{environment['python']}, Docker {environment['docker']}, PostgreSQL "
                f"{environment['postgres']}. Тесты: {tests['passed']} прошли "
                f"({tests['unit']} unit + {tests['integration']} integration), "
                f"{tests['failed']} упали, {tests['skipped']} пропущены.",
                f"Environment: {loc(environment['os'])}, uv {environment['uv']}, Python "
                f"{environment['python']}, Docker {environment['docker']}, PostgreSQL "
                f"{environment['postgres']}. Tests: {tests['passed']} passed "
                f"({tests['unit']} unit + {tests['integration']} integration), "
                f"{tests['failed']} failed, {tests['skipped']} skipped.",
            ),
            BODY_S,
        ),
        Spacer(1, 8),
        tight_table(
            [
                tr("Проверка", "Check"),
                tr("Команда", "Command"),
                tr("Результат", "Result"),
                tr("Статус", "Status"),
            ],
            [
                [
                    escape(loc(item["name"])),
                    mono(item["command"]),
                    escape(loc(item["result"])),
                    '<font color="#15803D"><b>PASS</b></font>'
                    if item["status"] == "pass"
                    else '<font color="#C2410C"><b>FAIL</b></font>',
                ]
                for item in verification["checks"]
            ],
            [74, 190, W - 310, 46],
        ),
        p(tr("Ответы сервера", "Server responses"), H2),
        tight_table(
            [tr("Запрос", "Request"), tr("Код", "Code"), tr("Тело", "Body")],
            [
                [
                    mono(loc(item["request"])),
                    escape(item["status"]),
                    mono(loc(item["body"])),
                ]
                for item in verification["http"]
            ],
            [168, 100, W - 268],
        ),
        Spacer(1, 8),
        callout(
            f"<b>GitHub Actions: {remote_label(remote['status'])}.</b> "
            + escape(loc(remote["detail"])),
            AMBER,
            AMBER_L,
        ),
    ]
    # «Что дальше» и пункты держатся вместе: заголовок не останется один внизу.
    next_steps = [p(tr("Что дальше", "What is next"), H2)]
    for item in verification["remaining"]:
        next_steps += [p("• " + escape(loc(item)), BODY_S), Spacer(1, 2)]
    story.append(KeepTogether(next_steps))
    return story
