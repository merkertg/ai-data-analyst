# Отчёт о проверке

Здесь записаны только фактически выполненные проверки. Локальные результаты
и удалённый GitHub Actions разделены: локальный успех не подтверждает CI.
Машиночитаемая сводка для PDF — [verification.json](guide/verification.json).

## Этап 01 — 2026-10-20, коммит `4448e55`

Окружение: macOS (Apple Silicon), uv 0.12.23, Python 3.12.15.

| Проверка | Команда | Результат |
| --- | --- | --- |
| Тесты | `uv run pytest` | 7 passed, 0 failed, 0 skipped, 0.27 с |
| Линтер | `uv run ruff check .` | All checks passed |
| Формат | `uv run ruff format --check .` | Все файлы отформатированы (включая Python-блоки в Markdown) |
| Типы | `uv run mypy app tests` | Success: no issues found in 6 source files |
| Lock | `uv lock --check` | lock соответствует `pyproject.toml` |
| Чистый клон | `git clone` → `uv sync --locked` → все проверки | PASS |
| Workflow | `actionlint 1.7.12` | Ошибок нет |
| Возраст пакетов | даты `upload-time` в `uv.lock` | 38 пакетов; самый новый — websockets 17.2 от 2026-10-03 |
| Сервер | `uvicorn app.main:app`, затем curl | `GET /health` → 200 `{"status":"ok"}`; `POST /health` → 405, `allow: GET`; `GET /nope` → 404; `/docs` → 200 HTML |

### PDF-руководство

- Сборка `scripts/build_guide.py` с ReportLab 4.4.9: 18 страниц A4.
- Все страницы отрендерены `pdftoppm` и просмотрены. Найденные при первой
  сборке недочёты исправлены: чёрная полоса в схеме HTTP, текст за краем
  панели, полупустые страницы, наложение подписей в схеме Git.
- Код, версии пакетов, шаги CI и OpenAPI-схема берутся из проекта при сборке.

### Эксперименты

Во временной копии проекта, не в репозитории:

- Тесты без `pythonpath` → `ModuleNotFoundError: No module named 'app'`
  в трёх тестовых модулях.
- `health()` возвращает `{"status": "fail"}`:
  - mypy — `Incompatible return value type (got "dict[str, str]", expected "HealthResponse")`;
  - pytest — `ResponseValidationError: Input should be 'ok'`;
  - клиент — `500 Internal Server Error`.

### Не проверено

- **GitHub Actions:** репозиторий на GitHub ещё не создан, удалённый запуск
  не выполнялся. Статус `not_verified`.
- Запуск на Linux и Windows вручную не проверялся. Linux проверит CI.
