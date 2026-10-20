# Проверка проекта

Дата проверки: **20 октября 2026 года**. Проверенная версия — коммит `4448e55`
(код этапа 01); документация и PDF добавлены коммитом `d3a43a5`.
Здесь записаны только фактически выполненные проверки. Локальные результаты
и удалённый GitHub Actions разделены: локальный успех не подтверждает CI.
Машиночитаемая сводка для PDF — [verification.json](guide/verification.json).

## 1. Что проверяется

| Область | Как проверяем | Где смотреть |
| --- | --- | --- |
| Зависимости | `uv sync --locked`, `uv lock --check`, даты `upload-time` в lock | `pyproject.toml`, `uv.lock` |
| Python-код и документация | Ruff: правила `E F I UP B`, форматирование `.py` и Python-блоков в `.md` | `pyproject.toml` |
| Типы | mypy `strict` с плагином Pydantic | `app/`, `tests/` |
| HTTP и настройки | 7 тестов pytest через TestClient | `tests/` |
| Настоящий сервер | Uvicorn и curl: `/health`, `POST /health`, неизвестный путь, `/docs` | [инструкция API](instructions/usage.md) |
| Воспроизводимость | Чистый клон коммита и полный набор команд CI | [инструкция тестирования](instructions/testing.md) |
| Workflow | actionlint 1.7.12 | `.github/workflows/ci.yml` |
| PDF | Пересборка, рендер всех страниц и визуальная проверка | [руководство и его исходник](guide/README.md) |

## 2. Исправления, найденные при проверке

### Тесты не находили пакет app

Тест из стартового задания курса падал на сборе:
`ModuleNotFoundError: No module named 'app'`. Uvicorn добавляет текущую папку
в `sys.path`, а `uv run pytest` — нет; проект создан с `--no-package`
и не установлен в `.venv`. Исправлено настройкой
`[tool.pytest.ini_options] pythonpath = ["."]`. Разбор — в
[руководстве этапа, раздел 5](STAGE_01.md#5-пакеты-модули-и-импорт).

### uv init создаёт другую структуру

В uv 0.12 `uv init` по умолчанию создаёт пакет-библиотеку
`src/ai_data_analyst/` с `[build-system]`. Проект пересоздан командой
`uv init --app --no-package`; решение записано в
[ADR 0001](adr/0001-application-layout-and-tooling.md).

### Предупреждение Starlette про httpx

Starlette 1.7 предупреждала, что `httpx` для TestClient устарел.
В группе `dev` он заменён на `httpx2`; предупреждения больше нет.

### Вёрстка PDF

При первой сборке найдены: чёрная полоса в шапках схемы HTTP, текст за краем
панели ответа, раздел, перенесённый на почти пустую страницу, наложение
подписей команд в схеме Git. Всё исправлено и проверено повторным рендером.

## 3. Как повторить проверку

В корне проекта:

```bash
uv sync --locked
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app tests
uv run --locked pytest -v
uvx --from actionlint-py actionlint .github/workflows/ci.yml
```

Проверка настоящего сервера: запусти `uv run --locked uvicorn app.main:app`
и выполни запросы из [инструкции API](instructions/usage.md).
Пересборка и проверка PDF — в [guide/README.md](guide/README.md).

## 4. Подтверждённые результаты

Окружение: macOS (Apple Silicon), uv 0.12.23, Python 3.12.15.

| Проверка | Команда | Результат |
| --- | --- | --- |
| Тесты | `uv run pytest` | **7 passed, 0 failed, 0 skipped**, 0.27 с |
| Линтер | `uv run ruff check .` | All checks passed |
| Формат | `uv run ruff format --check .` | Все файлы отформатированы, включая Python-блоки в Markdown |
| Типы | `uv run mypy app tests` | Success: no issues found in 6 source files |
| Lock | `uv lock --check` | lock соответствует `pyproject.toml` |
| Чистый клон | `git clone` → `uv sync --locked` → все проверки | PASS для `4448e55` и `d3a43a5` |
| Workflow | actionlint 1.7.12 | Ошибок нет |
| Возраст пакетов | даты `upload-time` в `uv.lock` | 38 пакетов; самый новый — websockets 17.2 от 2026-10-03 |
| Сервер | Uvicorn и curl | `GET /health` → 200 `{"status":"ok"}`; `POST /health` → 405, `allow: GET`; `GET /nope` → 404 `{"detail":"Not Found"}`; `/docs` → 200 HTML |
| PDF | ReportLab 4.4.9, `pdftoppm` | 18 страниц, все просмотрены |

### Эксперименты

Во временной копии проекта, не в репозитории:

- Тесты без `pythonpath` → `ModuleNotFoundError: No module named 'app'`
  в трёх тестовых модулях.
- `health()` возвращает `{"status": "fail"}`:
  - mypy — `Incompatible return value type (got "dict[str, str]", expected "HealthResponse")`;
  - pytest — `ResponseValidationError: Input should be 'ok'`;
  - клиент — `500 Internal Server Error`.

### GitHub Actions

Коммиты `4448e55` и `d3a43a5` отправлены в `main`. Результат задания
**Lint, types and tests** пока **не подтверждён**: репозиторий приватный,
статус проверяет пользователь. Подтверждение будет записано сюда, в
[CI_CD.md](CI_CD.md) и в `verification.json`.

## 5. Границы результата и следующий этап

Проверен только macOS локально; Linux проверит CI. Windows не проверялся.
Базы данных, данных и аналитики ещё нет, поэтому проверяется только каркас.

Следующий этап — PostgreSQL в Docker Compose, модели SQLAlchemy 2, первая
миграция Alembic и интеграционные тесты ограничений целостности.
