"""Bilingual sections 43–45: Docker stand, bootstrap and smoke test, CI/CD."""

from reportlab.platypus import Spacer

from guide.diagrams import cicd_flow, compose_stack
from guide.i18n import tr
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
    SMALL,
    TEAL,
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


def add_stage10(story):
    """Explain the image, the self-preparing stand and the delivery pipeline."""
    section(
        story,
        number_of("Docker-образ и стенд"),
        tr(
            "Одна команда: база, миграции, демо-данные, API и интерфейс.",
            "One command: database, migrations, demo data, API and interface.",
        ),
        TEAL,
    )
    story += [
        p(
            tr(
                "Критерий последнего этапа: другой разработчик клонирует "
                "репозиторий, выполняет docker compose up --build, открывает "
                "интерфейс и повторяет демонстрацию. Ни .env, ни загрузки данных, "
                "ни выдачи токена вручную не нужно.",
                "The final criterion: another developer clones the repository, "
                "runs docker compose up --build, opens the interface and repeats "
                "the demonstration. No .env, no data loading and no manual token.",
            )
        ),
        Diagram(112, compose_stack),
        Spacer(1, 6),
        code_block(
            "git clone git@github.com:merkertg/ai-data-analyst.git\n"
            "cd ai-data-analyst && docker compose up --build\n"
            "# UI http://127.0.0.1:8502 · API http://127.0.0.1:8001/docs"
        ),
        Spacer(1, 6),
        simple_table(
            [tr("Сервис", "Service"), tr("Что делает", "What it does")],
            [
                [
                    mono("db"),
                    tr(
                        "PostgreSQL 17 по digest; том postgres_data.",
                        "PostgreSQL 17 by digest; volume postgres_data.",
                    ),
                ],
                [
                    mono("migrate"),
                    tr(
                        "alembic upgrade head и выход.",
                        "alembic upgrade head, then exits.",
                    ),
                ],
                [
                    mono("bootstrap"),
                    tr(
                        "Демо-данные в пустую базу и токен интерфейса.",
                        "Demo data into an empty DB and the UI token.",
                    ),
                ],
                [
                    mono("api"),
                    tr(
                        "Uvicorn; готов, когда /ready отвечает 200.",
                        "Uvicorn; ready when /ready answers 200.",
                    ),
                ],
                [
                    mono("ui"),
                    tr(
                        "Streamlit; без настроек базы и ключа модели.",
                        "Streamlit; no database settings or model key.",
                    ),
                ],
            ],
            [110, W - 110],
            [CELL, CELL],
        ),
        p(tr("Образ", "The image"), H2),
        code_block(
            "FROM python:3.12-slim@sha256:a6e3… AS python-base\n"
            "FROM python-base AS builder\n"
            "COPY --from=ghcr.io/astral-sh/uv:0.12.23@sha256:61d3… /uv /bin/uv\n"
            "RUN uv sync --locked --no-dev\n"
            "FROM python-base AS runtime\n"
            "COPY --from=builder /app/.venv /app/.venv\n"
            "USER app   # UID 10001"
        ),
        Spacer(1, 6),
        p(
            tr(
                "uv и кеш остаются в builder; runtime получает .venv и код без "
                "dev-инструментов. Compose передаёт DATABASE_HOST, DATABASE_PORT, "
                "DATABASE_NAME, DATABASE_USER и DATABASE_PASSWORD только migrate, "
                "bootstrap и api. SQLAlchemy URL.create собирает адрес из компонентов: "
                "символы @, /, # и % в пароле передаются как есть, без ручного "
                "URL-кодирования. Интерфейс настроек базы не получает.",
                "uv and the cache stay in the builder; runtime gets .venv and code "
                "without dev tools. Compose passes DATABASE_HOST, DATABASE_PORT, "
                "DATABASE_NAME, DATABASE_USER and DATABASE_PASSWORD only to migrate, "
                "bootstrap and api. SQLAlchemy URL.create builds the connection URL "
                "from components: password characters @, /, # and % stay raw, with "
                "no manual URL encoding. The interface receives no database settings.",
            ),
            BODY_S,
        ),
    ]

    section(
        story,
        number_of("Подготовка и проверка стенда"),
        tr(
            "Подготовка безопасна при повторе; smoke проверяет то, что увидит человек.",
            "Bootstrap is safe to repeat; smoke checks what a person will see.",
        ),
        AMBER,
    )
    story += [
        simple_table(
            [tr("Шаг bootstrap", "Bootstrap step"), tr("Правило", "Rule")],
            [
                [
                    tr("Схема", "Schema"),
                    tr(
                        "Не последняя миграция — выход с ошибкой.",
                        "Not the latest migration — exit with an error.",
                    ),
                ],
                [
                    tr("Данные", "Data"),
                    tr(
                        "Пустая база — seed 42, 20 000 заказов; есть данные — ничего не менять.",
                        "Empty DB — seed 42, 20,000 orders; data present — change nothing.",
                    ),
                ],
                [
                    tr("Токен", "Token"),
                    tr(
                        "Оставить только действующий analyst; viewer, отозванный или испорченный — заменить.",
                        "Keep only a valid analyst; replace a viewer, revoked or broken token.",
                    ),
                ],
            ],
            [110, W - 110],
            [CELL, CELL],
        ),
        Spacer(1, 6),
        code_block(
            '{"demo_data": "loaded", "rows": {"orders": 20000, …}, "ui_token": "issued"}\n'
            '{"demo_data": "already present", "rows": null, "ui_token": "kept"}'
        ),
        p(tr("Интерфейс внутри Docker", "The interface inside Docker"), H2),
        p(
            tr(
                "http://api:8000 разрешён через UI_ALLOWED_API_HOSTS: только имя "
                "из одного слова, не домен или IP. UI_API_TOKEN_FILE указывает на "
                "том ui_token, доступный UI только для чтения. mkstemp создаёт "
                "уникальный файл с правами 0600; replace атомарно устанавливает "
                "токен, finally удаляет временный файл и при ошибке. Небезопасный "
                "файл действующего analyst переписывается с тем же токеном.",
                "http://api:8000 is allowed through UI_ALLOWED_API_HOSTS: a "
                "single-label name only, never a domain or IP. UI_API_TOKEN_FILE "
                "points to the ui_token volume, mounted read-only for the UI. "
                "mkstemp creates a unique mode-0600 file; replace installs the "
                "token atomically, and finally removes the temporary file even "
                "on failure. An unsafe valid analyst file is rewritten with "
                "the same token.",
            ),
            BODY_S,
        ),
        p(tr("Smoke-проверка", "Smoke test"), H2),
        p(
            tr(
                "scripts/smoke_stack.py, только стандартная библиотека: /health; "
                "/ready → 0004; 401 без токена; сентябрь 466678757.35, изменение "
                "−165497371.86 (−26.18 %); ответ агента с этим числом в "
                "доказательствах; запуск в истории; здоровье Streamlit.",
                "scripts/smoke_stack.py, standard library only: /health; /ready → "
                "0004; 401 without a token; September 466678757.35, change "
                "−165497371.86 (−26.18%); an agent answer with that number in its "
                "evidence; the run in history; Streamlit health.",
            ),
            BODY_S,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Текущая локальная проверка.</b> Отдельный тестовый стенд Compose "
                "собран и healthy за 23.5 с с зарезервированными символами в пароле. "
                "Smoke — 8/8 до и 8/8 после пересоздания; данные и токен сохранены. "
                "Это проверка локального образа, а не подтверждение публикации.",
                "<b>Current local check.</b> An isolated test Compose stand built "
                "and became healthy in 23.5 s with reserved characters in its "
                "password. Smoke: 8/8 before and 8/8 after re-creation; data and "
                "the token persisted. This verifies a local image, not publication.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    section(
        story,
        number_of("CI/CD и публикация"),
        tr(
            "В GHCR попадает только тот образ, что прошёл smoke-проверку.",
            "Only the image that passed the smoke test reaches GHCR.",
        ),
        VIOLET,
    )
    story += [
        Diagram(110, cicd_flow),
        Spacer(1, 6),
        simple_table(
            [tr("Задание", "Job"), tr("Что проверяет", "What it checks")],
            [
                [
                    "Lint, types and tests",
                    tr(
                        "Ruff: 197 файлов; mypy: 130. 690 тестов: 522 unit + 168 integration, 39.66 с; покрытие 94.12 %, порог 90 %.",
                        "Ruff: 197 files; mypy: 130. 690 tests: 522 unit + 168 integration, 39.66 s; coverage 94.12%, threshold 90%.",
                    ),
                ],
                [
                    "Audit runtime dependencies",
                    tr(
                        "Старый JSON удаляется; нужен свежий корректный отчёт и согласованный exit. Ошибка или неверное исключение блокирует сборку.",
                        "Old JSON is removed; a fresh valid report and matching exit status are required. An error or invalid exception blocks the build.",
                    ),
                ],
                [
                    "Build and smoke test Docker",
                    tr(
                        "UID 10001 без dev-инструментов; compose up; smoke; пересоздание; smoke.",
                        "UID 10001 without dev tools; compose up; smoke; re-creation; smoke.",
                    ),
                ],
                [
                    "Publish to GHCR",
                    tr(
                        "Тот же образ: :main, :sha-…; тег v1.2.3 только из main.",
                        "The same image: :main, :sha-…; tag v1.2.3 only from main.",
                    ),
                ],
            ],
            [170, W - 170],
            [CELL, CELL],
        ),
        p(tr("Аудит против политики 14 дней", "Audit versus the 14-day policy"), H2),
        p(
            tr(
                "Первый аудит нашёл 24 уязвимости Pillow 12.3.0 и одну certifi. "
                "Исправления вышли 16 и 20 октября, а Pillow 13 требует и Streamlit "
                "1.66 — всё моложе 14 дней. Политику сохранили: находки приняты "
                "до 6 ноября с причиной (проект не декодирует изображения, HTTPS "
                "только к OpenAI). Просроченное или лишнее исключение роняет аудит.",
                "The first audit found 24 Pillow 12.3.0 vulnerabilities and one in "
                "certifi. Fixes came out on 16 and 20 October, and Pillow 13 also "
                "needs Streamlit 1.66 — all younger than 14 days. The policy stays: "
                "findings are accepted until 6 November with a reason (no image "
                "decoding; HTTPS only to OpenAI). An expired or stale exception "
                "fails the audit.",
            ),
            BODY_S,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Права.</b> Запись в пакеты — только у задания публикации; "
                "токен стенда в журнале маскируется; действия закреплены SHA, "
                "образы — digest (это проверяют тесты). Успешный запуск GitHub "
                "Actions и публикация в GHCR сейчас не подтверждены.",
                "<b>Permissions.</b> Only the publish job may write packages; the "
                "stand token is masked in the log; actions are pinned by SHA and "
                "images by digest (tests check it). A successful GitHub Actions "
                "run and publication to GHCR are currently unconfirmed.",
            ),
            BLUE,
            BLUE_L,
        ),
        Spacer(1, 6),
        callout(
            tr(
                f"Курс завершён: десять этапов. Итоги — раздел {RESULTS}, "
                "docs/VERIFICATION.md и docs/PROJECT_STATUS_2026-10-22.md; показ — "
                "docs/DEMO.md.",
                f"The course is complete: ten stages. Results — section {RESULTS}, "
                "docs/VERIFICATION.md and docs/PROJECT_STATUS_2026-10-22.md; the "
                "demo — docs/DEMO.md.",
            ),
            GREEN,
            GREEN_L,
            SMALL,
        ),
    ]
