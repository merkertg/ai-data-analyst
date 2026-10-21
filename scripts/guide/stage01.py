"""Разделы 2–11: этап 01 — окружение, первый API, настройки, тесты, Git."""

from reportlab.platypus import PageBreak, Spacer

from guide.diagrams import (
    fixture_flow,
    git_flow,
    http_anatomy,
    import_paths,
    request_flow,
    settings_priority,
    uv_flow,
    validation_levels,
)
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
    TEAL,
    TEAL_L,
    VIOLET,
    VIOLET_L,
    Diagram,
    W,
    callout,
    cards,
    code_block,
    mono,
    p,
    simple_table,
)
from guide.sources import (
    MYPY_OUTPUT,
    RUFF_EXAMPLE,
    RUFF_OUTPUT,
    class_source,
    function_source,
    source_slice,
)
from guide.toc import section

DEPENDENCY_PURPOSE = {
    "alembic": ("миграции схемы", "schema migrations"),
    "fastapi": ("маршруты, проверка данных, /docs", "routes, validation, /docs"),
    "psycopg": ("драйвер PostgreSQL", "PostgreSQL driver"),
    "pydantic-settings": (
        "настройки из окружения и .env",
        "settings from env and .env",
    ),
    "sqlalchemy": ("модели, пул, сессии", "models, pool, sessions"),
    "uvicorn": ("ASGI-сервер, слушает порт", "ASGI server, listens on a port"),
    "httpx2": ("HTTP-клиент для TestClient", "HTTP client for TestClient"),
    "mypy": ("проверка типов", "type checking"),
    "pytest": ("запуск тестов", "running tests"),
    "ruff": ("линтер и форматировщик", "linter and formatter"),
    "starlette": ("веб-основа FastAPI", "web foundation of FastAPI"),
    "pydantic": ("модели и проверка данных", "models and validation"),
}


def add_stage01(story, verification, dependencies, lock_packages, facts):
    """Добавить в story разделы 2–11 об этапе 01."""
    tests = verification["tests"]

    # 2. Путь запроса
    section(
        story,
        2,
        tr(
            'Что происходит между нажатием Execute в /docs и ответом {"status": "ok"}.',
            'What happens between pressing Execute in /docs and the {"status": "ok"} reply.',
        ),
        TEAL,
    )
    story += [
        Diagram(186, request_flow),
        Spacer(1, 12),
        simple_table(
            [tr("Шаг", "Step"), tr("Кто", "Who"), tr("Что делает", "What it does")],
            [
                [
                    "1",
                    tr("Клиент", "Client"),
                    tr(
                        "Формирует HTTP-запрос GET /health и отправляет его на 127.0.0.1:8000.",
                        "Builds an HTTP request GET /health and sends it to 127.0.0.1:8000.",
                    ),
                ],
                [
                    "2",
                    "Uvicorn",
                    tr(
                        "Принимает соединение, разбирает HTTP и передаёт запрос приложению по протоколу ASGI.",
                        "Accepts the connection, parses HTTP and passes the request to the app over ASGI.",
                    ),
                ],
                [
                    "3",
                    "FastAPI",
                    tr(
                        "Ищет обработчик по паре «метод + путь». Для POST ответит 405, для неизвестного пути — 404.",
                        "Finds the handler by method and path. POST gets 405, an unknown path gets 404.",
                    ),
                ],
                [
                    "4",
                    "health()",
                    tr(
                        'Создаёт объект HealthResponse(status="ok").',
                        'Creates a HealthResponse(status="ok") object.',
                    ),
                ],
                [
                    "5",
                    "Pydantic",
                    tr(
                        "Проверяет объект по схеме ответа и превращает его в JSON.",
                        "Validates the object against the response schema and writes JSON.",
                    ),
                ],
            ],
            [34, 72, W - 106],
        ),
        p(tr("Фактический ответ сервера", "Actual server response"), H2),
        code_block(
            "$ curl -i http://127.0.0.1:8000/health\n"
            "HTTP/1.1 200 OK\n"
            "server: uvicorn\n"
            "content-length: 15\n"
            "content-type: application/json\n"
            "\n"
            '{"status":"ok"}'
        ),
        Spacer(1, 10),
        callout(
            tr(
                "<b>TestClient</b> в тестах подключается сразу к FastAPI (шаг 3): без "
                "сети, без Uvicorn и без свободного порта. Поэтому unit-тесты "
                "проходят за доли секунды.",
                "<b>TestClient</b> in tests connects straight to FastAPI (step 3): no "
                "network, no Uvicorn and no free port. That is why unit tests run "
                "in a fraction of a second.",
            ),
            TEAL,
            TEAL_L,
        ),
    ]

    # 3. Окружение и uv
    section(
        story,
        3,
        tr(
            "Как uv превращает список требований в одинаковое окружение на любом "
            "компьютере.",
            "How uv turns a list of requirements into the same environment on any "
            "computer.",
        ),
        VIOLET,
    )
    story += [
        Diagram(98, uv_flow),
        Spacer(1, 10),
        p(
            tr(
                "<b>Виртуальное окружение</b> " + mono(".venv") + " — отдельная папка "
                "со своим Python и библиотеками только для этого проекта. Так проекты "
                "не мешают друг другу. Системный " + mono("python3") + " на этом Mac — "
                "3.9.6; его не трогаем, всё запускаем через " + mono("uv run") + ".",
                "<b>A virtual environment</b> " + mono(".venv") + " is a separate "
                "folder with its own Python and libraries for this project only, so "
                "projects do not interfere. The system " + mono("python3") + " on "
                "this Mac is 3.9.6; we leave it alone and run everything with "
                + mono("uv run")
                + ".",
            ),
            BODY_S,
        ),
        Spacer(1, 8),
        simple_table(
            ["", "pyproject.toml", "uv.lock"],
            [
                [
                    tr("Кто пишет", "Written by"),
                    tr("Человек и команда uv add", "A person and uv add"),
                    tr("Только uv", "uv only"),
                ],
                [
                    tr("Что внутри", "Contents"),
                    tr(
                        "Требования: fastapi&gt;=0.142.2",
                        "Requirements: fastapi&gt;=0.142.2",
                    ),
                    tr("Точные версии и хэши файлов", "Exact versions and file hashes"),
                ],
                [
                    tr("Транзитивные пакеты", "Transitive packages"),
                    tr("Нет", "No"),
                    tr(
                        f"Да, все {lock_packages}: starlette, pydantic, anyio…",
                        f"Yes, all {lock_packages}: starlette, pydantic, anyio…",
                    ),
                ],
                [tr("В Git", "In Git"), tr("Да", "Yes"), tr("Да", "Yes")],
            ],
            [110, (W - 110) / 2, (W - 110) / 2],
        ),
        p(
            tr(
                "Зависимости проекта (версии из uv.lock)",
                "Project dependencies (versions from uv.lock)",
            ),
            H2,
        ),
        simple_table(
            [
                tr("Пакет", "Package"),
                tr("Версия", "Version"),
                tr("Группа", "Group"),
                tr("Зачем", "Purpose"),
            ],
            [
                [
                    mono(name),
                    mono(version),
                    group,
                    tr(*DEPENDENCY_PURPOSE.get(name, ("", ""))),
                ]
                for name, version, group in dependencies
            ],
            [118, 70, 70, W - 258],
            [CELL, CELL, CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            tr(
                "<b>Политика возраста пакетов.</b> "
                + mono('[tool.uv] exclude-newer = "2026-10-06T00:00:00Z"')
                + " — uv не видит выпуски PyPI новее этой даты. Свежий выпуск бывает "
                "сломан или даже вредоносен; за две недели такие проблемы обычно находят.",
                "<b>Package age policy.</b> "
                + mono('[tool.uv] exclude-newer = "2026-10-06T00:00:00Z"')
                + " — uv ignores PyPI releases newer than this date. A fresh release "
                "may be broken or even malicious; within two weeks such problems are "
                "usually found.",
            ),
            VIOLET,
            VIOLET_L,
        ),
    ]

    # 4. Создание проекта
    section(
        story,
        4,
        tr(
            "Какими командами создан проект, чем они отличаются от стартового задания "
            "и что лежит в каждой папке.",
            "Which commands created the project, how they differ from the starter task "
            "and what each folder holds.",
        ),
        ORANGE,
    )
    story += [
        code_block(
            tr(
                "# uv 0.12.23 — та же версия, что закреплена в CI\n",
                "# uv 0.12.23 — the same version as pinned in CI\n",
            )
            + "curl -LsSf https://astral.sh/uv/0.12.23/install.sh \\\n"
            "  | env UV_NO_MODIFY_PATH=1 sh\n"
            "\n"
            "uv init --app --no-package --python 3.12 --author-from none\n"
            "rm main.py && mkdir -p app tests\n"
            "uv add fastapi 'uvicorn[standard]' pydantic-settings\n"
            "uv add --dev pytest ruff mypy httpx2"
        ),
        Spacer(1, 10),
        cards(
            [
                (
                    tr("uv init в uv 0.12", "uv init in uv 0.12"),
                    tr(
                        "Без флагов создаёт пакет-библиотеку: src/ai_data_analyst/, [build-system] "
                        "и [project.scripts]. Для веб-сервиса с папкой app/ в корне нужен "
                        "--app --no-package.",
                        "Without flags it creates a library package: src/ai_data_analyst/, "
                        "[build-system] and [project.scripts]. A web service with app/ at the "
                        "root needs --app --no-package.",
                    ),
                    ORANGE,
                    ORANGE_L,
                ),
                (
                    tr("httpx2 вместо httpx", "httpx2 instead of httpx"),
                    tr(
                        "Starlette 1.7 предупреждает: «Using httpx with starlette.testclient is "
                        "deprecated; install httpx2 instead». TestClient работает на httpx2.",
                        "Starlette 1.7 warns: “Using httpx with starlette.testclient is "
                        "deprecated; install httpx2 instead”. TestClient runs on httpx2.",
                    ),
                    ORANGE,
                    ORANGE_L,
                ),
            ],
            columns=2,
        ),
        p(tr("Файлы этапа 01", "Stage 01 files"), H2),
        simple_table(
            [tr("Файл или папка", "File or folder"), tr("Для чего нужен", "Purpose")],
            [
                [
                    mono("app/__init__.py"),
                    tr(
                        'Делает app пакетом; хранит версию __version__ = "0.1.0".',
                        'Makes app a package; holds __version__ = "0.1.0".',
                    ),
                ],
                [
                    mono("app/config.py"),
                    tr(
                        "Класс Settings и функция get_settings().",
                        "The Settings class and get_settings().",
                    ),
                ],
                [
                    mono("app/main.py"),
                    tr(
                        "Объект FastAPI и служебные маршруты.",
                        "The FastAPI object and service routes.",
                    ),
                ],
                [
                    mono("tests/"),
                    tr(
                        "Тесты: API, настройки, версия; позже — база.",
                        "Tests: API, settings, version; later the database.",
                    ),
                ],
                [
                    mono("pyproject.toml"),
                    tr(
                        "Описание проекта, зависимости, настройки pytest, Ruff, mypy, uv.",
                        "Project metadata, dependencies, pytest/Ruff/mypy/uv settings.",
                    ),
                ],
                [
                    mono("uv.lock"),
                    tr(
                        f"Точные версии всех {lock_packages} пакетов.",
                        f"Exact versions of all {lock_packages} packages.",
                    ),
                ],
                [
                    mono(".python-version"),
                    tr(
                        "3.12 — какой Python выбирает uv.",
                        "3.12 — the Python uv selects.",
                    ),
                ],
                [
                    mono(".env.example"),
                    tr(
                        "Образец локальных настроек; сам .env — не в Git.",
                        "Local settings template; .env itself is not in Git.",
                    ),
                ],
                [
                    mono(".gitignore"),
                    tr(
                        "Что Git не отслеживает: .venv, кеши, .env.",
                        "What Git ignores: .venv, caches, .env.",
                    ),
                ],
                [
                    mono(".github/workflows/ci.yml"),
                    tr("Проверки в GitHub Actions.", "Checks in GitHub Actions."),
                ],
                [
                    mono("docs/"),
                    tr(
                        "Руководства, инструкции, CI/CD, подход, ADR, журнал, отчёт, PDF.",
                        "Guides, instructions, CI/CD, approach, ADRs, log, report, PDFs.",
                    ),
                ],
                [
                    mono("scripts/"),
                    tr(
                        "Сборка этого PDF на русском и английском.",
                        "Builds this PDF in Russian and English.",
                    ),
                ],
                [
                    mono("AGENTS.md"),
                    tr(
                        "Правила работы над проектом.", "Working rules for the project."
                    ),
                ],
            ],
            [160, W - 160],
            [CELL, CELL],
        ),
    ]

    # 5. Импорт и sys.path
    section(
        story,
        5,
        tr(
            "Почему сервер находит пакет app, а pytest без настройки — нет.",
            "Why the server finds the app package and pytest without a setting does not.",
        ),
        BLUE,
    )
    story += [
        p(
            tr(
                "<b>Модуль</b> — один файл " + mono(".py") + ". <b>Пакет</b> — папка с "
                "модулями; файл " + mono("__init__.py") + " выполняется при первом "
                "импорте пакета. <b>sys.path</b> — список папок, где Python ищет "
                "модули. Строка " + mono("from app.main import app") + " работает, "
                "только если в одной из этих папок лежит папка app.",
                "<b>A module</b> is one "
                + mono(".py")
                + " file. <b>A package</b> is a "
                "folder of modules; " + mono("__init__.py") + " runs on the first "
                "import. <b>sys.path</b> is the list of folders where Python looks for "
                "modules. " + mono("from app.main import app") + " works only if one "
                "of these folders contains the app folder.",
            ),
            BODY_S,
        ),
        Spacer(1, 10),
        Diagram(178, import_paths),
        Spacer(1, 10),
        p(tr("Фактическая ошибка до настройки", "Actual error before the setting"), H2),
        code_block(
            "$ uv run pytest\n"
            "ImportError while importing test module '.../tests/test_health.py'.\n"
            "E   ModuleNotFoundError: No module named 'app'\n"
            "Interrupted: 3 errors during collection"
        ),
        p(tr("Исправление в pyproject.toml", "The fix in pyproject.toml"), H2),
        code_block(
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["."]'
        ),
        Spacer(1, 10),
        callout(
            tr(
                "<b>Почему так.</b> Проект создан с --no-package: в .venv ставятся "
                "только зависимости, сам app не устанавливается. Другие решения — "
                "python -m pytest (флаг -m добавляет текущую папку) или оформить "
                "проект пакетом. Явная настройка работает при любом способе запуска.",
                "<b>Why.</b> The project was created with --no-package: .venv gets "
                "only the dependencies, app itself is not installed. Alternatives are "
                "python -m pytest (-m adds the current folder) or packaging the "
                "project. An explicit setting works however pytest is started.",
            ),
        ),
    ]

    # 6. HTTP и JSON
    http_facts = {item["request"]: item["status"] for item in verification["http"]}
    section(
        story,
        6,
        tr(
            "Из чего состоят запрос и ответ и какие коды встретятся в проекте.",
            "What a request and a response consist of and which codes the project uses.",
        ),
        TEAL,
    )
    story += [
        Diagram(132, http_anatomy),
        Spacer(1, 12),
        simple_table(
            [
                tr("Метод", "Method"),
                tr("Смысл", "Meaning"),
                tr("В этом проекте", "In this project"),
            ],
            [
                [
                    mono("GET"),
                    tr(
                        "Получить данные, ничего не меняя",
                        "Read data without changing it",
                    ),
                    tr(
                        "GET /health, GET /ready; позже GET /api/metrics/revenue",
                        "GET /health, GET /ready; later GET /api/metrics/revenue",
                    ),
                ],
                [
                    mono("POST"),
                    tr(
                        "Создать объект или запустить действие",
                        "Create an object or run an action",
                    ),
                    tr("позже — вопрос AI-агенту", "later: a question to the AI agent"),
                ],
                [
                    mono("PUT / PATCH"),
                    tr("Заменить или частично изменить", "Replace or partially update"),
                    tr("пока не используем", "not used yet"),
                ],
                [
                    mono("DELETE"),
                    tr("Удалить", "Delete"),
                    tr("пока не используем", "not used yet"),
                ],
            ],
            [86, 190, W - 276],
        ),
        Spacer(1, 10),
        simple_table(
            [
                tr("Код", "Code"),
                tr("Значение", "Meaning"),
                tr("Когда увидишь (проверено)", "When you see it (verified)"),
            ],
            [
                [
                    "200 OK",
                    tr("Успех", "Success"),
                    f"GET /health → {http_facts['GET /health']}",
                ],
                [
                    "404 Not Found",
                    tr("Такого пути нет", "No such path"),
                    f"GET /nope → {http_facts['GET /nope']}",
                ],
                [
                    "405 Method Not Allowed",
                    tr("Путь есть, метод не тот", "Path exists, wrong method"),
                    f"POST /health → {http_facts['POST /health']}, allow: GET",
                ],
                [
                    "422 Unprocessable Content",
                    tr("Неверные входные данные", "Invalid input"),
                    tr(
                        "появится на этапе 06 с параметрами запросов",
                        "arrives in Stage 06 with query parameters",
                    ),
                ],
                [
                    "500 Internal Server Error",
                    tr("Ошибка на сервере", "Server error"),
                    tr("эксперимент в разделе 7", "experiment in section 7"),
                ],
                [
                    "503 Service Unavailable",
                    tr("Сервис не готов", "Service not ready"),
                    tr(
                        "GET /ready без базы — раздел 18",
                        "GET /ready without a database — section 18",
                    ),
                ],
            ],
            [140, 130, W - 270],
        ),
        Spacer(1, 10),
        p(
            tr(
                "<b>JSON</b> — текстовый формат данных: объекты {...}, массивы [...], "
                "строки, числа, true / false / null. FastAPI превращает Pydantic-модель "
                "в JSON сам, а " + mono("response.json()") + " в тесте превращает JSON "
                "обратно в словарь Python.",
                "<b>JSON</b> is a text data format: objects {...}, arrays [...], "
                "strings, numbers, true / false / null. FastAPI turns a Pydantic model "
                "into JSON itself, and " + mono("response.json()") + " in a test turns "
                "JSON back into a Python dict.",
            ),
            BODY_S,
        ),
    ]

    # 7. Разбор кода API
    section(
        story,
        7,
        tr(
            "Маршрут /health построчно и эксперимент с неправильным ответом.",
            "The /health route line by line and an experiment with a wrong reply.",
        ),
    )
    story += [
        code_block(
            source_slice("app/main.py", "app = FastAPI(", ")")
            + "\n\n\n"
            + class_source("app/main.py", "HealthResponse")
            + "\n\n\n"
            + function_source("app/main.py", "health")
        ),
        Spacer(1, 10),
        simple_table(
            [tr("Фрагмент", "Fragment"), tr("Что делает", "What it does")],
            [
                [
                    mono("app = FastAPI(...)"),
                    tr(
                        "Объект приложения. Его находит Uvicorn (app.main:app) и вызывает TestClient. "
                        "title и version — в /docs; lifespan закрывает пул базы при остановке.",
                        "The application object. Uvicorn finds it (app.main:app) and TestClient "
                        "calls it. title and version go to /docs; lifespan closes the database "
                        "pool on shutdown.",
                    ),
                ],
                [
                    mono("class HealthResponse"),
                    tr(
                        'Pydantic-модель: описание формы ответа. Literal["ok"] разрешает ровно одно значение.',
                        'A Pydantic model describing the reply. Literal["ok"] allows exactly one value.',
                    ),
                ],
                [
                    mono('@app.get("/health")'),
                    tr(
                        "Регистрирует функцию для пары GET + /health. Другие методы получат 405.",
                        "Registers the function for GET + /health. Other methods get 405.",
                    ),
                ],
                [
                    mono("-> HealthResponse"),
                    tr(
                        "Аннотация возврата становится схемой ответа: по ней строится /docs и "
                        "проверяется результат функции.",
                        "The return annotation becomes the response schema: it drives /docs and "
                        "validates the function's result.",
                    ),
                ],
                [
                    mono(tr("def, не async def", "def, not async def")),
                    tr(
                        "Обычную функцию FastAPI выполняет в отдельном потоке. К async вернёмся на этапе 06.",
                        "FastAPI runs a plain function in a worker thread. We return to async in Stage 06.",
                    ),
                ],
            ],
            [150, W - 150],
            [CELL, CELL],
        ),
        PageBreak(),
        p(tr("Эксперимент: неправильный ответ", "Experiment: a wrong reply"), H2),
        p(
            tr(
                "Во временной копии проекта функция health() вернула "
                + mono('{"status": "fail"}')
                + ". Фактические результаты:",
                "In a temporary copy of the project health() returned "
                + mono('{"status": "fail"}')
                + ". Actual results:",
            ),
            BODY_S,
        ),
        Spacer(1, 8),
        Diagram(80, validation_levels),
        Spacer(1, 10),
        callout(
            tr(
                "<b>Два уровня защиты:</b> типы ловят ошибку в коде, Pydantic — в данных. "
                "Неправильный ответ не уходит клиенту молча. Для аналитики это главное: "
                "лучше явная ошибка, чем неверное число в отчёте.",
                "<b>Two layers of protection:</b> types catch the bug in code, Pydantic "
                "catches it in data. A wrong reply never reaches the client silently. "
                "For analytics this matters most: an explicit error beats a wrong number "
                "in a report.",
            ),
            GREEN,
            GREEN_L,
        ),
        p(tr("Модель → JSON → словарь", "Model → JSON → dict"), H2),
        p(
            tr(
                "FastAPI превращает объект модели в JSON-текст, а тест превращает JSON "
                "обратно в словарь Python. Значения получены из настоящего приложения "
                "при сборке PDF:",
                "FastAPI turns a model object into JSON text, and a test turns JSON back "
                "into a Python dict. The values come from the real application while the "
                "PDF is built:",
            ),
            BODY_S,
        ),
        Spacer(1, 6),
        code_block(
            '>>> HealthResponse(status="ok").model_dump_json()   # model → JSON\n'
            f"'{facts['model_json']}'\n"
            '>>> client.get("/health").json()                    # JSON → dict\n'
            "{'status': 'ok'}"
        ),
        p(tr("OpenAPI и страница /docs", "OpenAPI and the /docs page"), H2),
        p(
            tr(
                "FastAPI собирает описание маршрутов и моделей в документ OpenAPI ("
                + mono("GET /openapi.json")
                + "). Страница /docs — это Swagger UI, "
                "который рисует этот документ. Схема HealthResponse из приложения; "
                "docstring модели стал полем description:",
                "FastAPI collects routes and models into an OpenAPI document ("
                + mono("GET /openapi.json")
                + "). The /docs page is Swagger UI drawing "
                "that document. The HealthResponse schema from the app; the model "
                "docstring became the description field:",
            ),
            BODY_S,
        ),
        Spacer(1, 6),
        code_block(facts["schema"]),
    ]

    # 8. Настройки
    section(
        story,
        8,
        tr(
            "Конфигурация живёт в окружении, а не в коде.",
            "Configuration lives in the environment, not in the code.",
        ),
        TEAL,
    )
    story += [
        Diagram(140, settings_priority),
        Spacer(1, 10),
        code_block(
            source_slice(
                "app/config.py",
                "class Settings(BaseSettings):",
                'app_name: str = "AI Data Analyst"',
            )
            + "\n    ...\n\n\n"
            + function_source("app/config.py", "get_settings")
        ),
        Spacer(1, 8),
        simple_table(
            [tr("Тест", "Test"), tr("Что закрепляет", "What it pins down")],
            [
                [
                    mono("test_default_app_name"),
                    tr(
                        "Без окружения и .env берётся значение из кода.",
                        "Without env and .env the code default wins.",
                    ),
                ],
                [
                    mono("test_env_file_overrides_default"),
                    tr(
                        "Строка в .env заменяет значение по умолчанию.",
                        "A line in .env replaces the default.",
                    ),
                ],
                [
                    mono("test_environment_variable_beats_env_file"),
                    tr(
                        "Переменная окружения важнее строки в .env.",
                        "An environment variable beats .env.",
                    ),
                ],
            ],
            [230, W - 230],
            [CELL, CELL],
        ),
        Spacer(1, 8),
        callout(
            tr(
                '<b>extra="ignore"</b> — в .env лежат и переменные Docker (POSTGRES_*), '
                "не относящиеся к Settings. <b>get_settings()</b> читает настройки "
                "один раз на процесс, поэтому изменения .env видны после перезапуска "
                "сервера. На этапе 02 добавлен database_url — раздел 12.",
                '<b>extra="ignore"</b> — .env also holds Docker variables (POSTGRES_*) '
                "unrelated to Settings. <b>get_settings()</b> reads settings once per "
                "process, so .env changes apply after a server restart. Stage 02 "
                "added database_url — section 12.",
            ),
            TEAL,
            TEAL_L,
        ),
    ]

    # 9. Тесты API
    section(
        story,
        9,
        tr(
            "Как pytest находит тесты, что такое фикстура и что доказывает каждый тест этапа 01.",
            "How pytest finds tests, what a fixture is and what each Stage 01 test proves.",
        ),
        GREEN,
    )
    story += [
        p(
            tr(
                "Pytest находит файлы " + mono("test_*.py") + " в папке tests/ и "
                "выполняет функции с именем " + mono("test_...") + ". Внутри обычный "
                "assert: если условие ложно, pytest покажет, какие значения не "
                "совпали. Фикстура — подготовка для теста; тест получает её, объявив "
                "параметр с тем же именем.",
                "Pytest finds " + mono("test_*.py") + " files in tests/ and runs "
                "functions named " + mono("test_...") + ". Inside is a plain assert: "
                "when it fails, pytest shows which values differ. A fixture prepares "
                "a test; the test gets it by declaring a parameter with the same name.",
            ),
            BODY_S,
        ),
        Spacer(1, 8),
        Diagram(68, fixture_flow),
        Spacer(1, 10),
        code_block(function_source("tests/test_health.py", "client")),
        Spacer(1, 10),
        simple_table(
            [tr("Тест", "Test"), tr("Что доказывает", "What it proves")],
            [
                [
                    mono("test_health_returns_ok"),
                    tr(
                        'GET /health → 200 и ровно {"status": "ok"}',
                        'GET /health → 200 and exactly {"status": "ok"}',
                    ),
                ],
                [mono("test_health_rejects_post"), "POST /health → 405"],
                [
                    mono("test_openapi_describes_health"),
                    tr(
                        "Схема знает версию, путь и поле status",
                        "The schema knows the version, path and status",
                    ),
                ],
                [
                    mono("test_default_app_name"),
                    tr("Умолчание из кода", "Code default"),
                ],
                [
                    mono("test_env_file_overrides_default"),
                    tr(".env важнее умолчания", ".env beats the default"),
                ],
                [
                    mono("test_environment_variable_beats_env_file"),
                    tr("Окружение важнее .env", "Environment beats .env"),
                ],
                [
                    mono("test_version_matches_pyproject"),
                    tr(
                        "app.__version__ совпадает с pyproject.toml",
                        "app.__version__ matches pyproject.toml",
                    ),
                ],
            ],
            [230, W - 230],
            [CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            tr(
                f"Это 7 тестов этапа 01. Сейчас в проекте {tests['unit']} unit-тестов и "
                f"{tests['integration']} интеграционных. Проверки этапов 02–04 — "
                "в разделах 20, 23 и 26.",
                f"These are the 7 Stage 01 tests. The project now has {tests['unit']} "
                f"unit and {tests['integration']} integration tests. Checks for "
                "Stages 02–04 are in sections 20, 23 and 26.",
            ),
            GREEN,
            GREEN_L,
        ),
    ]

    # 10. Ruff и mypy
    section(
        story,
        10,
        tr(
            "Два инструмента, которые находят ошибки до запуска программы.",
            "Two tools that find bugs before the program runs.",
        ),
        VIOLET,
    )
    story += [
        simple_table(
            [tr("Правило Ruff", "Ruff rule"), tr("Что ищет", "What it finds")],
            [
                [mono("E"), tr("Нарушения стиля PEP 8", "PEP 8 style violations")],
                [
                    mono("F"),
                    tr(
                        "Ошибки: неиспользуемые импорты, неопределённые имена",
                        "Errors: unused imports, undefined names",
                    ),
                ],
                [mono("I"), tr("Порядок импортов", "Import order")],
                [
                    mono("UP"),
                    tr(
                        "Устаревший синтаксис, который в Python 3.12 проще",
                        "Old syntax that is simpler in Python 3.12",
                    ),
                ],
                [
                    mono("B"),
                    tr(
                        "Типичные ловушки, например изменяемое значение аргумента по умолчанию",
                        "Common traps such as a mutable default argument",
                    ),
                ],
            ],
            [100, W - 100],
            [CELL, CELL],
        ),
        Spacer(1, 8),
        p(
            tr(
                mono("ruff check .")
                + " ищет проблемы, с "
                + mono("--fix")
                + " исправляет "
                "безопасные; "
                + mono("ruff format --check .")
                + " проверяет формат, в том "
                "числе Python-блоков в Markdown. <b>mypy strict</b> требует аннотации у "
                "каждой функции; теперь он проверяет и " + mono("migrations/") + ".",
                mono("ruff check .")
                + " finds problems, "
                + mono("--fix")
                + " fixes the "
                "safe ones; " + mono("ruff format --check .") + " checks formatting, "
                "including Python blocks in Markdown. <b>mypy strict</b> requires "
                "annotations on every function; it now also checks "
                + mono("migrations/")
                + ".",
            ),
            BODY_S,
        ),
        p(tr("Пример: что находит Ruff", "Example: what Ruff finds"), H2),
        code_block(RUFF_EXAMPLE),
        Spacer(1, 6),
        code_block(RUFF_OUTPUT),
        p(
            tr(
                "I001 — порядок импортов, F401 — неиспользуемый импорт, UP035 и UP006 — "
                "List вместо list, B006 — общий список по умолчанию, который копит "
                "значения между вызовами. Пометка [*] — Ruff исправит сам через --fix.",
                "I001 import order, F401 unused import, UP035 and UP006 List instead of "
                "list, B006 a shared default list that accumulates values between calls. "
                "[*] means Ruff fixes it with --fix.",
            ),
            SMALL,
        ),
        p(tr("Пример: что находит mypy", "Example: what mypy finds"), H2),
        code_block(MYPY_OUTPUT),
    ]

    # 11. Git и GitHub
    section(
        story,
        11,
        tr(
            "Что хранится в репозитории и как изменения попадают на GitHub.",
            "What the repository stores and how changes reach GitHub.",
        ),
        BLUE,
    )
    story += [
        Diagram(64, git_flow),
        Spacer(1, 12),
        cards(
            [
                (
                    tr("В Git", "In Git"),
                    tr(
                        "Код app/, tests/, migrations/, sql/, pyproject.toml, uv.lock, compose.yaml, "
                        "alembic.ini, .env.example, workflow, документация и PDF.",
                        "Code in app/, tests/, migrations/, sql/, pyproject.toml, uv.lock, "
                        "compose.yaml, alembic.ini, .env.example, the workflow, docs and PDFs.",
                    ),
                    GREEN,
                    GREEN_L,
                ),
                (
                    tr("Не в Git", "Not in Git"),
                    tr(
                        ".venv (пересоздаётся uv sync), кеши инструментов, .env с паролем базы "
                        "и будущими ключами, данные PostgreSQL в томе Docker.",
                        ".venv (rebuilt by uv sync), tool caches, .env with the database password "
                        "and future keys, PostgreSQL data in the Docker volume.",
                    ),
                    ORANGE,
                    ORANGE_L,
                ),
            ],
            columns=2,
        ),
        p(tr("Публикация", "Publishing"), H2),
        p(
            tr(
                "Репозиторий: <b>merkertg/ai-data-analyst</b>, ветка main. Для нового "
                "проекта: на github.com <b>New repository</b> без README, .gitignore и "
                "лицензии, затем:",
                "Repository: <b>merkertg/ai-data-analyst</b>, branch main. For a new "
                "project: <b>New repository</b> on github.com without README, .gitignore "
                "or license, then:",
            ),
            BODY_S,
        ),
        Spacer(1, 4),
        code_block(
            "git remote add origin git@github.com:<login>/<repository>.git\n"
            "git push -u origin main"
        ),
        Spacer(1, 6),
        p(
            tr(
                "Дальше каждое изменение: "
                + mono("git add")
                + " → "
                + mono("git commit")
                + " → "
                + mono("git push origin main")
                + ". Вкладка <b>Actions</b> "
                "показывает результат CI; только он подтверждает удалённую проверку.",
                "Then every change: "
                + mono("git add")
                + " → "
                + mono("git commit")
                + " → "
                + mono("git push origin main")
                + ". The <b>Actions</b> tab shows "
                "the CI result; only it confirms the remote check.",
            ),
            BODY_S,
        ),
        Spacer(1, 10),
        callout(
            tr(
                "Сообщения коммитов — на английском, в повелительном наклонении: «Add …», "
                "«Fix …». Каждый коммит — законченный шаг, после которого проходят все "
                "проверки.",
                "Commit messages are in English and imperative: “Add …”, “Fix …”. Each "
                "commit is a finished step after which all checks pass.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]
