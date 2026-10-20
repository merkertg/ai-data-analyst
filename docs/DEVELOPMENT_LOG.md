# Журнал разработки

Здесь записаны изменения и фактические проверки каждого этапа.
Пошаговое учебное объяснение находится в [STAGE_01.md](STAGE_01.md),
устройство pipeline — в [CI_CD.md](CI_CD.md).

## 2026-10-20 — этап 01: подготовка проекта

Цель: минимальное приложение с правильной структурой, тестами, статическими
проверками и базовым CI — фундамент, на который лягут база данных,
аналитика и AI-агент.

| Шаг | Что изменено | Файлы | Проверка и результат |
| --- | --- | --- | --- |
| 1. Установка uv | uv 0.12.23 официальным установщиком в `~/.local/bin` с `UV_NO_MODIFY_PATH=1`: папка уже есть в `PATH`. Python 3.12.15, ранее скачанный uv, переиспользован. | — | `uv --version` → `uv 0.12.23`; `uv run python --version` → `Python 3.12.15`. |
| 2. Создание проекта | `uv init --app --no-package --python 3.12 --author-from none`. Обычный `uv init` в uv 0.12 создаёт пакет со структурой `src/` — нам нужен `app/` в корне. | `pyproject.toml`, `.python-version`, `.gitignore`, `README.md` | Первый `uv init` без флагов создал `src/ai_data_analyst/` и `[build-system]`; проект пересоздан с нужными флагами. |
| 3. Зависимости | Политика возраста пакетов `exclude-newer = 2026-10-06`; FastAPI, Uvicorn, pydantic-settings; в `dev` — pytest, Ruff, mypy, httpx2. | `pyproject.toml`, `uv.lock` | 38 пакетов в lock; самый новый — websockets 17.2 от 2026-10-03. `uv lock --check` успешен. |
| 4. Замена httpx | `httpx` из плана курса заменён на `httpx2`. | `pyproject.toml`, `uv.lock` | Starlette 1.7 выводила `Using httpx with starlette.testclient is deprecated; install httpx2 instead`; после замены предупреждения нет. |
| 5. Приложение | Версия в `app/__init__.py`; `Settings` с приоритетом окружение → `.env` → умолчание; FastAPI и `GET /health` с моделью `HealthResponse`. | `app/__init__.py`, `app/config.py`, `app/main.py`, `.env.example` | Uvicorn: `GET /health` → 200 `{"status":"ok"}`, `POST /health` → 405 с `allow: GET`, `GET /nope` → 404, `/docs` → 200. |
| 6. Тесты | 7 тестов: HTTP-ответы, OpenAPI-схема, приоритет настроек, совпадение версий. | `tests/` | До настройки `pythonpath`: `ModuleNotFoundError: No module named 'app'` в 3 модулях. После: **7 passed, 0 skipped**, 0.27 с. |
| 7. Статические проверки | Ruff (`E`, `F`, `I`, `UP`, `B`), формат; mypy `strict` с плагином Pydantic. | `pyproject.toml` | `All checks passed`; все файлы отформатированы; `Success: no issues found in 6 source files`. |
| 8. CI | Workflow `CI`: uv 0.12.23, `uv sync --locked`, Ruff, mypy, pytest; действия закреплены SHA, права только на чтение. | `.github/workflows/ci.yml` | actionlint 1.7.12 — ошибок нет. Команды CI прошли в чистом клоне коммита `4448e55`. |
| 9. Документация | Руководство этапа, инструкции, CI/CD, подход, ADR, журнал, отчёт. | `docs/`, `README.md`, `AGENTS.md` | Внутренние ссылки существуют; Python-блоки в Markdown проходят `ruff format --check`. |
| 10. PDF-руководство | Генератор на ReportLab 4.4.9: 18 страниц, код, версии и OpenAPI-схема берутся из проекта. | `scripts/build_guide.py`, `docs/guide/` | Все страницы отрендерены и просмотрены; найденные дефекты вёрстки исправлены. |

### Подтверждённые локальные результаты

- `uv sync --locked` завершился успешно, 38 пакетов.
- Pytest: **7 тестов прошли, пропущенных нет**.
- Ruff не нашёл нарушений; форматирование всех файлов, включая Python-блоки
  в Markdown, соответствует правилам.
- mypy в строгом режиме не нашёл ошибок в 6 файлах.
- Настоящий Uvicorn ответил на четыре проверочных запроса.
- Чистый клон каждого коммита этапа проходит весь набор команд CI.
- Эксперимент во временной копии: при ответе `{"status": "fail"}` mypy
  сообщил о несовпадении типа, FastAPI — `ResponseValidationError`,
  клиент получил `500 Internal Server Error`.

### Подтверждение на GitHub

Коммиты `4448e55` и `d3a43a5` отправлены в `main` репозитория
`merkertg/ai-data-analyst`. Результат GitHub Actions ещё не подтверждён:
репозиторий приватный, его статус проверяет пользователь во вкладке Actions.

### Граница этапа

Базы данных, демонстрационных данных, аналитики и LLM нет. Проверены только
macOS локально и Linux через CI (после подтверждения). Самостоятельное
задание этапа — маршрут `GET /version` — оставлено для практики.
