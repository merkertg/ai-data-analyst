# Этап 01. Подготовка проекта: подробное руководство

Этот документ объясняет всё, что создано на первом этапе: зачем нужен каждый
файл, как устроен каждый фрагмент кода и как самому всё запустить и проверить.
Команды выполняются в Terminal из папки `ai-data-analyst`, если не сказано иное.

Наглядная версия этого материала со схемами — в
[PDF-руководстве](guide/ai-data-analyst-guide.pdf). Короткие английские
инструкции без объяснений — в [docs/instructions/](instructions/):
[быстрый запуск](instructions/quickstart.md),
[API](instructions/usage.md), [проверки](instructions/testing.md),
[CI](instructions/ci-and-delivery.md),
[структура проекта](instructions/project-structure.md).

Быстрые переходы: [запуск](#3-как-запустить-на-mac) ·
[uv и зависимости](#4-окружение-и-зависимости-uv) ·
[импорт и ловушка pytest](#5-пакеты-модули-и-импорт) ·
[разбор кода API](#7-разбор-appmainpy) ·
[тесты](#9-тесты-pytest-и-testclient) ·
[типичные ошибки](#13-типичные-ошибки) ·
[проверь себя](#14-проверь-себя).

## 1. Что получилось на этом этапе

Приложение пока умеет одно: отвечать на служебный запрос `GET /health`.
Зато вокруг этой маленькой функции уже собран весь каркас будущего проекта:

| Что | Где | Зачем |
| --- | --- | --- |
| API на FastAPI | `app/main.py` | Принимает HTTP-запросы, отдаёт JSON, строит `/docs` |
| Настройки | `app/config.py` | Читает параметры из окружения и `.env`, а не из кода |
| Версия | `app/__init__.py` | Одно место для версии кода |
| 7 тестов | `tests/` | Проверяют API, настройки и совпадение версий |
| Ruff | `pyproject.toml` | Стиль, типичные ошибки, порядок импортов, форматирование |
| mypy (strict) | `pyproject.toml` | Проверяет типы до запуска программы |
| CI | `.github/workflows/ci.yml` | Повторяет все проверки на GitHub при каждом push |
| Зависимости | `pyproject.toml`, `uv.lock` | Точные версии библиотек для всех, кто клонирует проект |

Главная цепочка, которую нужно понять на этом этапе:

```text
Браузер или curl → HTTP-запрос → Uvicorn → FastAPI → функция health()
                → HealthResponse → проверка Pydantic → JSON-ответ
```

Базы данных, данных о продажах, аналитики и LLM пока нет. Они появятся
на этапах 02–07.

## 2. Карта файлов

```text
ai-data-analyst/
├── app/                      # Python-пакет приложения
│   ├── __init__.py           # версия кода: __version__ = "0.1.0"
│   ├── config.py             # класс Settings и объект settings
│   └── main.py               # объект FastAPI и маршрут GET /health
├── tests/
│   ├── test_config.py        # откуда берутся настройки
│   ├── test_health.py        # HTTP-ответы и OpenAPI-схема
│   └── test_version.py       # версия в коде = версия в pyproject.toml
├── docs/
│   ├── instructions/         # короткие инструкции: запуск, API, проверки, CI
│   ├── STAGE_01.md           # это руководство
│   ├── CI_CD.md              # подробно о GitHub Actions
│   ├── APPROACH.md           # задача, принципы, архитектура (англ.)
│   ├── adr/                  # записи архитектурных решений (англ.)
│   ├── DEVELOPMENT_LOG.md    # журнал: что сделано и как проверено
│   ├── VERIFICATION.md       # отчёт о фактических проверках
│   └── guide/                # PDF-руководство и данные для него
├── scripts/build_guide.py    # сборка PDF-руководства
├── .github/workflows/ci.yml  # GitHub Actions
├── .env.example              # образец локальных настроек (в Git)
├── .gitignore                # что Git не отслеживает
├── .python-version           # 3.12 — какой Python выбирает uv
├── pyproject.toml            # описание проекта и настройки инструментов
├── uv.lock                   # точные версии всех 38 пакетов
├── AGENTS.md                 # правила работы над проектом
└── .venv/                    # локальное окружение, в Git не попадает
```

Файлы с точкой в начале имени (`.env.example`, `.gitignore`, `.venv`) Finder
по умолчанию скрывает. Показать их: `Cmd + Shift + .` в окне Finder.

## 3. Как запустить на Mac

### Шаг 1. uv

uv — менеджер Python-проектов: ставит нужную версию Python, создаёт
виртуальное окружение, устанавливает библиотеки и запускает команды внутри
окружения. На этом Mac uv 0.12.23 установлен официальным установщиком
в `~/.local/bin` — та же версия закреплена в CI:

```bash
curl -LsSf https://astral.sh/uv/0.12.23/install.sh | env UV_NO_MODIFY_PATH=1 sh
```

`UV_NO_MODIFY_PATH=1` запрещает установщику менять `~/.zshrc`: папка
`~/.local/bin` уже есть в `PATH`. Проверка:

```bash
uv --version
```

Ожидается `uv 0.12.23 (...)`. Если терминал пишет `command not found`, открой
новую вкладку Terminal.

### Шаг 2. Окружение

```bash
cd ~/Desktop/"AI Forge"/ai-data-analyst
uv sync --locked
uv run python --version
```

`uv sync --locked` создаёт `.venv` и ставит туда библиотеки ровно тех версий,
что записаны в `uv.lock`. Вторая команда должна вывести `Python 3.12.15`.
Обрати внимание: системный `python3` на этом Mac — 3.9.6. Его мы не трогаем
и не используем; всё запускаем через `uv run`.

### Шаг 3. Сервер

```bash
uv run uvicorn app.main:app --reload
```

`app.main:app` читается так: «в модуле `app/main.py` возьми переменную `app`».
`--reload` перезапускает сервер при изменении `.py`-файлов. В выводе появится:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Этот Terminal теперь занят сервером. Для других команд открой вторую вкладку.

### Шаг 4. Проверка в браузере

1. Открой <http://127.0.0.1:8000/docs> — интерактивную документацию Swagger UI.
2. Раскрой `GET /health`, нажми **Try it out**, затем **Execute**.
3. В блоке Response увидишь код `200` и тело `{"status": "ok"}`.
4. Ниже, в разделе **Schemas**, раскрой `HealthResponse` — это схема ответа,
   которую FastAPI построил из Pydantic-модели.

### Шаг 5. Проверка через curl

```bash
curl -i http://127.0.0.1:8000/health
```

Фактический ответ:

```text
HTTP/1.1 200 OK
server: uvicorn
content-length: 15
content-type: application/json

{"status":"ok"}
```

Флаг `-i` показывает строку статуса и заголовки, а не только тело. Остановить
сервер: `Ctrl + C` в его вкладке.

### Шаг 6. Все проверки

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
```

Ожидаемый результат: `7 passed`, `All checks passed!`, `... files already
formatted`, `Success: no issues found in 6 source files`.

## 4. Окружение и зависимости: uv

### Зачем виртуальное окружение

Каждому проекту нужны свои библиотеки своих версий. Если ставить всё в один
системный Python, проекты начнут мешать друг другу: первому нужен FastAPI одной
версии, второму — другой. Виртуальное окружение `.venv` — это отдельная папка
со своим Python и своими библиотеками для одного проекта. `uv run <команда>`
запускает команду именно внутри `.venv` этого проекта.

### pyproject.toml и uv.lock

| | `pyproject.toml` | `uv.lock` |
| --- | --- | --- |
| Кто пишет | Человек (и `uv add`) | Только uv |
| Что содержит | Что нужно проекту: `fastapi>=0.142.2` | Что именно установить: `fastapi 0.142.2` + хэши файлов |
| Транзитивные пакеты | Нет | Да — все 38, включая starlette, pydantic, anyio |
| В Git | Да | Да |

`pyproject.toml` описывает намерение, `uv.lock` фиксирует результат. Благодаря
lock-файлу CI на GitHub и любой, кто клонирует проект, получат точно те же
версии, что на твоём Mac. Хэши защищают от подмены файла пакета.

`.venv` в Git не попадает: его можно в любой момент пересоздать командой
`uv sync --locked`, а внутри лежат бинарные файлы именно для macOS arm64.

### Разбор pyproject.toml

```toml
[project]
name = "ai-data-analyst"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.142.2",            # маршруты API, проверка данных, /docs
    "pydantic-settings>=2.15.0",   # настройки из окружения и .env
    "uvicorn[standard]>=0.54.0",   # ASGI-сервер
]
```

- `requires-python` — проект не запустится на Python ниже 3.12.
- `uvicorn[standard]` — квадратные скобки означают «extras»: дополнительные
  пакеты для быстрой работы (`uvloop`, `httptools`) и для `--reload`
  (`watchfiles`).

```toml
[dependency-groups]
dev = ["httpx2>=2.13.1", "mypy>=2.4.0", "pytest>=9.1.1", "ruff>=0.16.10"]
```

Группа `dev` — инструменты разработчика. `uv sync` ставит её по умолчанию,
а в production-образ (этап 10) она не попадёт: серверу не нужен pytest.

```toml
[tool.uv]
exclude-newer = "2026-10-06T00:00:00Z"
```

Политика возраста зависимостей, как в первом проекте: uv «не видит» выпуски
PyPI новее этой даты. Свежий выпуск иногда оказывается сломанным или даже
вредоносным; за две недели такие проблемы обычно обнаруживают и выпуск отзывают.
Самый свежий пакет в нашем lock — `websockets 17.2` от 3 октября 2026 года.

### Основные команды uv

| Команда | Что делает |
| --- | --- |
| `uv add fastapi` | Добавить зависимость в `pyproject.toml`, обновить lock и `.venv` |
| `uv add --dev pytest` | То же для группы `dev` |
| `uv remove --dev httpx` | Удалить зависимость |
| `uv sync --locked` | Привести `.venv` в соответствие с lock; ошибка, если lock устарел |
| `uv lock --check` | Только проверить, что lock соответствует `pyproject.toml` |
| `uv run <команда>` | Выполнить команду внутри окружения проекта |
| `uv tree --depth 1` | Показать прямые зависимости и их версии |

### Два отличия от стартового плана курса

1. **`uv init` в uv 0.12 по умолчанию создаёт пакет со структурой `src/`**:
   `src/ai_data_analyst/__init__.py`, раздел `[build-system]` и команду
   `[project.scripts]`. Так оформляют библиотеки, которые публикуют на PyPI.
   Наш проект — приложение с папкой `app/` в корне, как в плане курса и в первом
   проекте, поэтому он создан командой:

   ```bash
   uv init --app --no-package --python 3.12 --author-from none
   ```

   `--no-package` значит, что сам проект не устанавливается в `.venv` как
   пакет: ставятся только его зависимости. Это и приводит к ловушке из
   [раздела 5](#5-пакеты-модули-и-импорт).
2. **`httpx2` вместо `httpx`.** Starlette 1.7 (основа FastAPI) при работе
   TestClient с `httpx` выводит предупреждение
   `Using httpx with starlette.testclient is deprecated; install httpx2 instead`.
   Поэтому в группе `dev` стоит `httpx2`.

## 5. Пакеты, модули и импорт

- **Модуль** — один файл `.py`. `app/config.py` — модуль `app.config`.
- **Пакет** — папка с модулями. Файл `__init__.py` делает папку обычным
  пакетом и выполняется при первом импорте пакета. У нас в нём записана версия:
  `from app import __version__` берёт её оттуда.
- **`sys.path`** — список папок, в которых Python ищет модули при импорте.
  Строка `from app.main import app` работает, только если в одной из этих папок
  лежит папка `app`.

### Почему сервер находит app, а pytest — нет

Uvicorn при запуске сам добавляет текущую папку в `sys.path` (опция
`--app-dir`, по умолчанию — текущая папка). Поэтому `uvicorn app.main:app`
из корня проекта работает.

`uv run pytest` запускает pytest как отдельную программу из `.venv/bin`.
Pytest добавляет в `sys.path` папку самого теста (`tests/`), но не корень
проекта. Проект установлен с `--no-package`, поэтому в `.venv` пакета `app`
тоже нет. Результат — фактическая ошибка до настройки:

```text
ImportError while importing test module '.../tests/test_health.py'.
E   ModuleNotFoundError: No module named 'app'
Interrupted: 3 errors during collection
```

Решение — одна строка в `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

Pytest добавляет корень проекта в `sys.path` до импорта тестов. Есть и другие
решения: запускать `python -m pytest` (флаг `-m` добавляет текущую папку)
или оформить проект как устанавливаемый пакет. Мы выбрали явную настройку:
она работает одинаково при любом способе запуска.

## 6. HTTP, JSON и REST

HTTP-запрос состоит из **метода**, **пути**, **заголовков** и необязательного
**тела**. Ответ — из **кода статуса**, **заголовков** и **тела**.

| Метод | Смысл | Пример в проекте |
| --- | --- | --- |
| `GET` | Получить данные, ничего не меняя | `GET /health`, позже `GET /api/metrics/revenue` |
| `POST` | Создать объект или запустить действие | позже `POST /api/agent/questions` |
| `PUT`/`PATCH` | Заменить / частично изменить | пока не используем |
| `DELETE` | Удалить | пока не используем |

| Код | Значение | Когда увидишь |
| --- | --- | --- |
| `200 OK` | Успех | `GET /health` |
| `404 Not Found` | Такого пути нет | `GET /nope` |
| `405 Method Not Allowed` | Путь есть, метод не тот | `POST /health` |
| `422 Unprocessable Content` | Неверные входные данные | появится на этапе 06 |
| `500 Internal Server Error` | Ошибка на сервере | см. эксперимент в разделе 7 |

Фактический ответ на `POST /health` — заголовок `allow` подсказывает,
какие методы разрешены:

```text
HTTP/1.1 405 Method Not Allowed
allow: GET
content-type: application/json

{"detail":"Method Not Allowed"}
```

**JSON** — текстовый формат данных: объекты `{...}`, массивы `[...]`, строки,
числа, `true`/`false`/`null`. FastAPI превращает Pydantic-модель в JSON сам,
а `response.json()` в тесте превращает JSON обратно в словарь Python.

## 7. Разбор app/main.py

```python
"""Точка входа API: создаём приложение FastAPI и служебный маршрут /health."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app import __version__
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description="AI-powered business analytics platform for IndustrialFlow",
    version=__version__,
)


class HealthResponse(BaseModel):
    """Ответ проверки живости: процесс запущен и отвечает на HTTP-запросы."""

    status: Literal["ok"]


@app.get("/health")
def health() -> HealthResponse:
    """Сообщить, что API работает; базу данных этот маршрут не проверяет."""
    return HealthResponse(status="ok")
```

Построчно:

1. **Импорты** разделены на три группы пустыми строками: стандартная библиотека
   (`typing`), сторонние пакеты (`fastapi`, `pydantic`), наш код (`app`).
   Этот порядок проверяет правило Ruff `I`.
2. **`app = FastAPI(...)`** — объект приложения. Его находит Uvicorn
   (`app.main:app`) и вызывает TestClient. `title`, `description` и `version`
   попадают в OpenAPI-схему и в заголовок страницы `/docs`.
3. **`class HealthResponse(BaseModel)`** — Pydantic-модель, то есть описание
   формы данных. `status: Literal["ok"]` разрешает в поле ровно одну строку
   `"ok"`.
4. **`@app.get("/health")`** — декоратор регистрирует функцию как обработчик
   пары «метод GET + путь `/health`». Для других методов на этом пути FastAPI
   сам ответит `405`.
5. **`-> HealthResponse`** — FastAPI использует аннотацию возврата как схему
   ответа (`response_model`): по ней строится документация и **проверяется
   то, что функция вернула**.
6. **`def`, а не `async def`.** Обычную функцию FastAPI выполняет в отдельном
   потоке, чтобы она не блокировала сервер. Для функций без ожидания
   ввода-вывода разница несущественна; к `async` вернёмся на этапе 06.

### Эксперимент: что если вернуть неправильный ответ

Во временной копии проекта функция `health()` возвращала `{"status": "fail"}`.
Фактические результаты:

- **mypy** нашёл ошибку до запуска:
  `Incompatible return value type (got "dict[str, str]", expected "HealthResponse")`.
- **Во время работы** FastAPI проверил ответ по схеме и отказался его отправлять:
  `ResponseValidationError: Input should be 'ok'` — а клиент получил
  `500 Internal Server Error`.

Это два уровня защиты: типы ловят ошибку в коде, Pydantic — в данных.
Неправильный ответ не уходит клиенту молча. В аналитическом проекте это
особенно важно: лучше явная ошибка, чем неверное число в отчёте.

### OpenAPI и /docs

FastAPI собирает описание всех маршрутов и моделей в документ OpenAPI
(`GET /openapi.json`). Страница `/docs` — это Swagger UI, который рисует этот
документ. Фактическая схема нашей модели:

```json
{
  "title": "HealthResponse",
  "type": "object",
  "required": ["status"],
  "properties": {"status": {"type": "string", "const": "ok", "title": "Status"}}
}
```

Docstring модели тоже попадает в схему как `description`.

## 8. Настройки: app/config.py

Правило: **конфигурация живёт в окружении, а не в коде**. Адрес базы данных,
ключ OpenAI, режим работы различаются на ноутбуке, в CI и на сервере, а код
везде один.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Data Analyst"


settings = Settings()
```

- **`BaseSettings`** — Pydantic-модель, которая заполняет поля из переменных
  окружения. Имена не зависят от регистра: `app_name` ← `APP_NAME`.
- **Приоритет**: переменная окружения → строка в `.env` → значение по
  умолчанию. Каждое правило закреплено отдельным тестом.
- **`extra="ignore"`** — позже в `.env` появятся переменные для Docker
  и PostgreSQL, которые к `Settings` не относятся. Без этой опции Pydantic
  отклонил бы их как неизвестные поля.
- **`settings = Settings()`** — объект создаётся один раз при импорте модуля.
  Следствие: изменения в `.env` вступают в силу только после перезапуска
  сервера (`--reload` следит за `.py`-файлами, а не за `.env`).

`.env` и `.env.example`: настоящий `.env` — в `.gitignore` (позже там будут
пароли и ключи), а образец `.env.example` хранится в Git и показывает, какие
переменные существуют.

Попробуй:

```bash
APP_NAME="IndustrialFlow Analytics" uv run uvicorn app.main:app
```

Заголовок на странице `/docs` сменится на «IndustrialFlow Analytics».

## 9. Тесты: pytest и TestClient

Pytest находит файлы `test_*.py` в папке `tests/` и выполняет функции,
имя которых начинается с `test_`. Внутри используется обычный `assert`:
если условие ложно, pytest показывает, какие значения не совпали.

### TestClient

`TestClient(app)` отправляет запросы **прямо в объект приложения**, без сети
и без Uvicorn. Тесты быстрые (все семь — за 0.3 секунды) и не требуют
свободного порта. Внутри TestClient работает на `httpx2`.

### Фикстуры

```python
@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
```

Фикстура — подготовка для теста. Тест получает её, просто объявив параметр
с тем же именем: `def test_health_returns_ok(client: TestClient)`. Код до
`yield` выполняется перед тестом, после `yield` — после теста. Встроенные
фикстуры pytest, которые мы используем:

- `monkeypatch` — временно меняет переменные окружения и сам всё возвращает;
- `tmp_path` — новая пустая папка для каждого теста.

### Семь тестов

| Тест | Что доказывает |
| --- | --- |
| `test_health_returns_ok` | `GET /health` → `200` и ровно `{"status": "ok"}` |
| `test_health_rejects_post` | `POST /health` → `405`: маршрут только для чтения |
| `test_openapi_describes_health` | Схема знает версию, путь и обязательное поле `status` |
| `test_default_app_name` | Без окружения и `.env` берётся значение из кода |
| `test_env_file_overrides_default` | Строка в `.env` заменяет умолчание |
| `test_environment_variable_beats_env_file` | Переменная окружения важнее `.env` |
| `test_version_matches_pyproject` | `app.__version__` совпадает с `pyproject.toml` |

Каждый тест построен по схеме «подготовка → действие → проверка»
(Arrange-Act-Assert), части разделены пустыми строками. Полезные флаги:
`uv run pytest -v` (каждый тест отдельной строкой), `-k config` (только тесты
с `config` в имени), `-x` (остановиться на первой ошибке).

## 10. Качество кода: Ruff и mypy

**Ruff** — линтер и форматировщик. Правила в `pyproject.toml`:

| Код | Что ищет |
| --- | --- |
| `E` | Нарушения стиля PEP 8 |
| `F` | Ошибки: неиспользуемые импорты, неопределённые имена |
| `I` | Порядок импортов |
| `UP` | Устаревший синтаксис, который в Python 3.12 пишется проще |
| `B` | Типичные ловушки, например изменяемое значение аргумента по умолчанию |

`ruff check .` ищет проблемы (`--fix` исправит безопасные), `ruff format .`
переформатирует код, `ruff format --check .` только проверяет. Ruff 0.16
форматирует и Python-блоки внутри Markdown, поэтому примеры кода в этой
документации тоже проходят проверку.

**mypy** проверяет типы, не запуская программу. Режим `strict = true` требует
аннотации у каждой функции и запрещает незаметные `Any`. Плагин
`pydantic.mypy` объясняет mypy, какие аргументы принимают модели и настройки.
Пример пользы — эксперимент из раздела 7.

## 11. CI: GitHub Actions

CI (continuous integration) — автоматический запуск проверок на сервере
GitHub при каждом изменении. Он защищает от ситуации «у меня работает»:
проект собирается с нуля на чистой Linux-машине.

Файл `.github/workflows/ci.yml`:

1. **Когда запускается**: push в `main`, pull request в `main`, ручной запуск
   (`workflow_dispatch`). Локальный `git commit` CI не запускает.
2. **`permissions: contents: read`** — заданию разрешено только читать код.
3. **`concurrency`** — новый push в тот же PR отменяет устаревшую проверку.
4. **Шаги**: получить код → поставить uv 0.12.23 и Python 3.12 →
   `uv sync --locked` → Ruff lint → Ruff format → mypy → pytest.
5. **Действия закреплены полным SHA**:
   `actions/checkout@3d3c42e…  # v7.0.1`. Тег `v7` автор может перенести на
   другой код, а SHA коммита изменить нельзя. Комментарий с версией — для людей.

Workflow проверен локально линтером `actionlint 1.7.12` — ошибок нет.
Те же команды прошли в чистом клоне коммитов `4448e55` и `d3a43a5`.
Оба коммита отправлены на GitHub; результат задания в Actions записывается
в [отчёт о проверке](VERIFICATION.md) после подтверждения.

Подробно о событиях, шагах, правах и разборе красного pipeline —
в [руководстве CI/CD](CI_CD.md).

## 12. Git и GitHub

В Git попадают исходники, `pyproject.toml`, `uv.lock`, `.python-version`,
`.env.example`, документация и workflow. Не попадают `.venv`, кеши
инструментов и `.env` — это записано в `.gitignore`.

Этап зафиксирован двумя коммитами: первый — код, тесты, настройки и CI
(`4448e55 Set up FastAPI project with health check, settings, tests and CI`),
второй — это руководство, журнал, отчёт и PDF. История: `git log --oneline`.

### Как опубликовать на GitHub

Репозиторий создан: [merkertg/ai-data-analyst](https://github.com/merkertg/ai-data-analyst),
удалённый адрес `origin` — `git@github.com:merkertg/ai-data-analyst.git` (SSH).
Для нового проекта порядок такой:

1. На github.com нажми **New repository** **без** README, `.gitignore`
   и лицензии — иначе история на GitHub разойдётся с локальной.
2. Подключи удалённый репозиторий и отправь ветку:

```bash
git remote add origin git@github.com:<логин>/<репозиторий>.git
git push -u origin main
```

3. Открой вкладку **Actions**: задание **Lint, types and tests** должно стать
   зелёным. Только после этого CI можно считать подтверждённым.

Дальше каждое изменение отправляется командой `git push origin main`.

## 13. Типичные ошибки

| Симптом | Причина | Что сделать |
| --- | --- | --- |
| `uv: command not found` | Терминал открыт до установки | Новая вкладка Terminal |
| `ModuleNotFoundError: No module named 'app'` | Нет `pythonpath` или запуск не из корня | Проверь `pyproject.toml`, выполни `cd` в корень |
| `Address already in use` | Порт 8000 занят другим сервером | `lsof -i :8000`, или `--port 8001` |
| `405 Method Not Allowed` | Не тот HTTP-метод | Для `/health` — только `GET` |
| `404 Not Found` | Опечатка в пути | Сверь путь с `/docs` |
| `uv sync --locked` падает | `pyproject.toml` изменён, lock — нет | `uv lock`, затем закоммить `uv.lock` |
| Изменения в `.env` не видны | Настройки читаются при старте | Перезапусти сервер |
| `python3 --version` → 3.9.6 | Это системный Python | Запускай через `uv run` |
| Предупреждение про `httpx` | Starlette 1.7 ждёт `httpx2` | Уже исправлено в `dev` |

## 14. Проверь себя

### Вопросы

1. Чем `pyproject.toml` отличается от `uv.lock`? Почему коммитим оба,
   а `.venv` — нет?
2. Почему Uvicorn находит пакет `app`, а pytest без настройки — нет?
   Что именно делает `pythonpath = ["."]`?
3. Что произойдёт, если `health()` вернёт `{"status": "fail"}`?
   Кто заметит ошибку первым?
4. Чем Uvicorn отличается от FastAPI?
5. В каком порядке `Settings` выбирает значение `app_name`?
6. Почему действия в CI закреплены SHA, а не тегом `v7`?

<details>
<summary>Ответы</summary>

1. В `pyproject.toml` — требования (нижние границы версий прямых
   зависимостей), в `uv.lock` — точные версии и хэши всех 38 пакетов.
   Оба нужны, чтобы любой получил то же окружение. `.venv` пересоздаётся
   из lock командой `uv sync --locked` и зависит от платформы.
2. Uvicorn добавляет текущую папку в `sys.path`; pytest добавляет папку теста
   `tests/`, а проект не установлен как пакет. `pythonpath = ["."]` добавляет
   корень проекта в `sys.path` до импорта тестов.
3. Первым ошибку найдёт mypy (несовпадение типа возврата). Если запустить
   код, FastAPI выбросит `ResponseValidationError`, клиент получит `500`.
4. FastAPI — приложение: маршруты, проверка данных, документация. Uvicorn —
   сервер: слушает порт, принимает HTTP-соединения и передаёт запросы
   в приложение по протоколу ASGI.
5. Переменная окружения → строка в `.env` → значение по умолчанию в коде.
6. Тег можно переписать на другой код (в том числе вредоносный),
   SHA коммита — нет.

</details>

### Самостоятельное задание

Добавь маршрут `GET /version`, который возвращает:

```json
{"name": "AI Data Analyst", "version": "0.1.0"}
```

Требования:

- ответ описан Pydantic-моделью `VersionResponse`;
- `name` берётся из `settings.app_name`, `version` — из `app.__version__`;
- есть тест на код `200` и тело ответа;
- `uv run pytest`, `ruff check`, `ruff format --check` и `mypy` проходят.

Подсказка: маршрут устроен так же, как `/health`.

## 15. Что дальше

Этап 02 — PostgreSQL в Docker Compose, модели SQLAlchemy 2 для клиентов,
товаров, заказов, позиций и возвратов, первая миграция Alembic и проверка
ограничений целостности.
