# Проверка проекта

Дата последней проверки: **20 октября 2026 года**, этапы 01–02,
код этапа 02 — коммит `cc7d851`.
Здесь записаны только фактически выполненные проверки. Локальные результаты
и удалённый GitHub Actions разделены: локальный успех не подтверждает CI.
Машиночитаемая сводка для PDF — [verification.json](guide/verification.json).

Разделы 1–5 описывают текущее состояние (этап 02). Раздел 6 сохранён как
история проверки этапа 01: числа в нём относятся к коммиту `4448e55`.

## 1. Что проверяется

| Область | Как проверяем | Где смотреть |
| --- | --- | --- |
| Зависимости | `uv sync --locked`, `uv lock --check`, даты `upload-time` в lock | `pyproject.toml`, `uv.lock` |
| Python-код и документация | Ruff: правила `E F I UP B`, форматирование `.py` и Python-блоков в `.md` | `pyproject.toml` |
| Типы | mypy `strict` с плагином Pydantic | `app/`, `tests/`, `migrations/` |
| HTTP и настройки | Unit-тесты через TestClient, без базы | `tests/*.py` |
| Схема и миграции | `alembic upgrade head`, `alembic check`, `downgrade base` → `upgrade head` | `migrations/`, [инструкция Database](instructions/database.md) |
| Целостность данных | 20 плохих строк отвергаются ожидаемым ограничением; правила удаления | `tests/integration/test_constraints.py` |
| SQL-запросы | Четыре файла `sql/` на учебном наборе дают ответы, посчитанные вручную | `tests/integration/test_queries.py` |
| Настоящий сервер | Uvicorn и curl: `/health`, `/ready` при работающей, остановленной и перезапущенной базе | [инструкция API](instructions/usage.md) |
| Сохранность данных | `docker compose down` без `-v` и новый `up` | `compose.yaml` |
| Воспроизводимость | Чистый клон коммита и полный набор команд CI | [инструкция тестирования](instructions/testing.md) |
| Workflow | actionlint 1.7.12 | `.github/workflows/ci.yml` |
| PDF | Сборка на русском и английском, рендер всех страниц и визуальная проверка | [руководство и его исходник](guide/README.md) |

## 2. Исправления, найденные при проверке

### Этап 02

- **Шаблон миграций и Ruff.** Стандартная строка шаблона
  `${imports if imports else ""}` оставляла лишнюю пустую строку, и Ruff
  отклонял сгенерированный файл (`I001`). Шаблон переписан через
  `% if imports:` — новые миграции сразу проходят проверку.
- **Номера заказов учебного набора.** При общей загрузке SQLAlchemy сама
  выбирала порядок вставки, и номера заказов в выводе SQL перемешивались
  (1, 4, 3). Связь «клиент → заказы» тянула за собой соседние заказы.
  Теперь каждый заказ сохраняется сразу после создания: номера 1–5 идут
  по порядку описания.
- **Маркер integration.** `--strict-markers` остановил сбор тестов, пока
  маркер не был объявлен в `pyproject.toml`.
- **Типы в тестах.** mypy нашёл сравнение несовместимых типов строк
  результата SQLAlchemy 2.1 и обращение к `sqltext` у общего `Constraint`;
  исправлено явными типами.

- **PDF на двух языках.** При первой сборке нашлись: символ `⇔`, которого
  нет в PT Sans (рисовался пустым квадратом), слипшиеся подписи `1` и `N`
  в ER-схеме, стрелки поверх таблицы на схеме двойного подсчёта, заголовки
  запросов, оторванные от кода, строка `export` за краем блока, перенос
  итогов на лишнюю страницу. Всё исправлено и проверено повторным рендером.

### Этап 01

- **Тесты не находили пакет app** без `pythonpath = ["."]` — разбор
  в [руководстве этапа 01](STAGE_01.md#5-пакеты-модули-и-импорт).
- **uv init создаёт другую структуру** в uv 0.12 — проект создан с
  `--app --no-package` ([ADR 0001](adr/0001-application-layout-and-tooling.md)).
- **Предупреждение Starlette про httpx** — заменён на `httpx2`.
- **Вёрстка PDF** — чёрная полоса в схеме HTTP, текст за краем панели,
  полупустые страницы, наложение подписей; исправлено повторным рендером.

## 3. Как повторить проверку

В корне проекта, с запущенным Docker Desktop:

```bash
uv sync --locked
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app tests migrations
docker compose --profile test up --detach --wait db-test
export TEST_DATABASE_URL='postgresql+psycopg://analyst:analyst_test@127.0.0.1:5437/industrialflow_test'
export DATABASE_URL="$TEST_DATABASE_URL"
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked alembic downgrade base
uv run --locked alembic upgrade head
CI=true uv run --locked pytest -v
uvx --from actionlint-py actionlint .github/workflows/ci.yml
```

Проверка настоящего сервера: запусти `db`, примени миграции к базе
разработки и выполни запросы из [инструкции API](instructions/usage.md).
Пересборка и проверка PDF — в [guide/README.md](guide/README.md).

## 4. Подтверждённые результаты

Окружение: macOS (Apple Silicon), uv 0.12.23, Python 3.12.15,
Docker 29.8.2, PostgreSQL 17 (`postgres:17@sha256:2d2b8998…`).

| Проверка | Команда | Результат |
| --- | --- | --- |
| Тесты | `pytest` с `TEST_DATABASE_URL` | **60 passed** (26 unit + 34 integration), около 1.2 с |
| Тесты без базы | `pytest` без `TEST_DATABASE_URL` | 26 passed, 34 skipped |
| Строгий режим CI | `CI=true pytest` без `TEST_DATABASE_URL` | Интеграционные тесты завершаются ошибкой, а не пропуском |
| Линтер | `ruff check .` | All checks passed |
| Формат | `ruff format --check .` | Все файлы отформатированы, включая Python-блоки в Markdown |
| Типы | `mypy app tests migrations` | Success: no issues found in 22 source files |
| Lock | `uv lock --check` | 45 пакетов, lock соответствует `pyproject.toml` |
| Миграции | `upgrade head`, `check`, `downgrade base`, `upgrade head` | Все успешны; `No new upgrade operations detected.` |
| Схема | `\dt` в psql | 6 таблиц и `alembic_version`; 28 именованных ограничений, 7 индексов |
| Ограничения | psql: `quantity = 0`, удаление товара с остатками | `ck_order_items_quantity_positive`, `fk_inventory_snapshots_product_id_products` |
| SQL-запросы | `psql < sql/*.sql` на учебном наборе | 190 000.00 / 120 000.00 / 18 000.00; сентябрь 309 000.00, октябрь 17 500.00; наивный JOIN 338 000.00 вместо 328 000.00 |
| `/ready` | Uvicorn, curl | 200 `{"status":"ready","revision":"0001"}`; после `stop db` — 503 `{"detail":"Database is not ready"}`; после `start db` — снова 200 |
| Сохранность | `docker compose down` → `up` | Контейнер сменился, 5 заказов и версия `0001` сохранились |
| Workflow | actionlint 1.7.12 | Ошибок нет |
| Чистый клон | `git clone` → `uv sync --locked` → все шаги CI | PASS для коммита кода этапа 02 `cc7d851`: 60 passed |
| PDF | ReportLab 4.4.9, `pdftoppm`, `pdftotext` | Русская и английская версии по 28 страниц, все страницы просмотрены; в английской нет русского текста вне кода и учебных данных |

### GitHub Actions

Коммиты этапа 01 и документации (`4448e55`, `d3a43a5`, `c22f342`)
отправлены в `main`. Результат задания **Lint, types and tests** пока
**не подтверждён**: репозиторий приватный, статус проверяет пользователь.
Коммит этапа 02 добавляет в задание PostgreSQL и тоже требует отдельного
подтверждения после push.

## 5. Границы результата и следующий этап

- Проверены macOS локально и (после подтверждения) Linux в CI; Windows
  не проверялся.
- Данные — только учебный набор из 5 заказов; объёмы и производительность
  запросов не измерялись.
- Правила, охватывающие несколько таблиц (сумма возвратов позиции,
  возврат только по оплаченному заказу), базой не проверяются — это задача
  проверок качества данных этапа 03.

Следующий этап — генерация демонстрационного датасета с внедрёнными
аномалиями, эталоном `ground_truth.json` и проверками качества данных.

## 6. История: проверка этапа 01 (коммит `4448e55`)

| Проверка | Результат на тот момент |
| --- | --- |
| Тесты | 7 passed, 0 failed, 0 skipped, 0.27 с |
| Ruff, формат | All checks passed; все файлы отформатированы |
| mypy | Success: no issues found in 6 source files |
| Lock | 38 пакетов; самый новый — websockets 17.2 от 2026-10-03 |
| Чистый клон | PASS для `4448e55` и `d3a43a5` |
| Сервер | `GET /health` → 200 `{"status":"ok"}`; `POST /health` → 405, `allow: GET`; `GET /nope` → 404 `{"detail":"Not Found"}`; `/docs` → 200 HTML |

Эксперименты во временной копии проекта: без `pythonpath` — `ModuleNotFoundError:
No module named 'app'`; при ответе `{"status": "fail"}` mypy сообщил
`Incompatible return value type`, FastAPI — `ResponseValidationError`,
клиент получил `500 Internal Server Error`.
