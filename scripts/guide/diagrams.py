"""Схемы PDF-гайда. Каждая функция рисует одну схему на холсте ReportLab.

Подписи задаются парами tr(русский, английский); язык выбирается до сборки.
"""

from reportlab.pdfbase import pdfmetrics

from guide.i18n import tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BLUE,
    BLUE_L,
    GREEN,
    GREEN_L,
    INK,
    LINE,
    MUTED,
    ORANGE,
    ORANGE_L,
    SLATE_L,
    SOFT,
    TEAL,
    TEAL_L,
    VIOLET,
    VIOLET_L,
    WHITE,
    arrow,
    chip,
    circle_num,
    draw_text,
    lines_in,
    node,
    poly_arrow,
    rbox,
)

# Сколько этапов курса уже выполнено: зелёные карточки дорожной карты.
STAGES_DONE = 7


def agent_loop(c, w, h):
    """The runtime between the model, the tools, the evidence check and history."""
    gap, bh = 22, 44
    bw = (w - 2 * gap) / 3
    top, low = h - bh - 4, 16
    xs = [index * (bw + gap) for index in range(3)]
    node(
        c,
        xs[0],
        top,
        bw,
        bh,
        tr("Вопрос", "Question"),
        "POST /api/agent/runs",
        SLATE_L,
        MUTED,
    )
    node(
        c,
        xs[1],
        top,
        bw,
        bh,
        "Runtime",
        tr("шаги, вызовы, время", "steps, calls, time"),
        BLUE_L,
        BLUE,
    )
    node(
        c,
        xs[2],
        top,
        bw,
        bh,
        tr("Модель", "Model"),
        tr("mock или OpenAI", "mock or OpenAI"),
        VIOLET_L,
        VIOLET,
    )
    node(
        c,
        xs[0],
        low,
        bw,
        bh,
        "agent_runs",
        tr("отчёт или ошибка + след", "report or error + trace"),
        GREEN_L,
        GREEN,
    )
    node(
        c,
        xs[1],
        low,
        bw,
        bh,
        tr("9 инструментов", "9 tools"),
        tr("SQL только для чтения", "read-only SQL"),
        TEAL_L,
        TEAL,
    )
    node(
        c,
        xs[2],
        low,
        bw,
        bh,
        tr("Проверка", "Evidence check"),
        tr("числа = результаты", "numbers = results"),
        AMBER_L,
        AMBER,
    )
    arrow(c, xs[0] + bw + 2, top + bh / 2, xs[1] - 2, top + bh / 2)
    # History goes to the model; calls or a report come back.
    arrow(c, xs[1] + bw + 2, top + bh * 0.68, xs[2] - 2, top + bh * 0.68, BLUE)
    arrow(c, xs[2] - 2, top + bh * 0.32, xs[1] + bw + 2, top + bh * 0.32, VIOLET)
    middle = xs[1] + bw / 2
    arrow(c, middle - 14, top - 2, middle - 14, low + bh + 2, BLUE)
    arrow(c, middle + 14, low + bh + 2, middle + 14, top - 2, TEAL)
    arrow(c, xs[2] + bw / 2, top - 2, xs[2] + bw / 2, low + bh + 2, VIOLET)
    poly_arrow(
        c,
        [
            (xs[2] + bw / 2, low - 2),
            (xs[2] + bw / 2, 6),
            (xs[0] + bw / 2, 6),
            (xs[0] + bw / 2, low - 2),
        ],
        GREEN,
    )


def api_flow(c, w, h):
    """HTTP request path: validation first, then a lazy session and the core."""
    gap, bh = 14, 47
    bw = (w - 3 * gap) / 4
    top_y = h - bh - 5
    items = [
        (
            tr("Клиент", "Client"),
            tr("curl, UI, агент", "curl, UI, agent"),
            SLATE_L,
            MUTED,
        ),
        ("Pydantic", tr("проверка параметров", "parameter checks"), VIOLET_L, VIOLET),
        (
            tr("Маршрут и сервис", "Route and service"),
            "app/api, app/services",
            BLUE_L,
            BLUE,
        ),
        (
            tr("Ядро и PostgreSQL", "Core and PostgreSQL"),
            "REPEATABLE READ",
            TEAL_L,
            TEAL,
        ),
    ]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, top_y, bw, bh, title, sub, fill, edge)
        if index < len(items) - 1:
            arrow(c, x + bw + 2, top_y + bh / 2, x + bw + gap - 2, top_y + bh / 2)
    bottom = [
        (1, "422", tr("до первого SQL", "before any SQL"), AMBER_L, AMBER),
        (
            2,
            "reports",
            tr("POST: снимок в JSONB", "POST: JSONB snapshot"),
            GREEN_L,
            GREEN,
        ),
        (3, "503", tr("база недоступна", "database unavailable"), ORANGE_L, ORANGE),
    ]
    for column, title, sub, fill, edge in bottom:
        x = column * (bw + gap)
        node(c, x, 5, bw, bh, title, sub, fill, edge)
        arrow(c, x + bw / 2, top_y - 2, x + bw / 2, 5 + bh + 2, edge)


def anomaly_flow(c, w, h):
    """Separate runtime database detection from offline answer-key evaluation."""
    gap, bh = 18, 47
    bw = (w - 2 * gap) / 3
    top_y = h - bh - 5
    items = [
        ("PostgreSQL", tr("текущие данные", "current data"), TEAL_L, TEAL),
        (
            tr("Детекторы", "Detectors"),
            tr("SQL/Decimal + модель", "SQL/Decimal + model"),
            VIOLET_L,
            VIOLET,
        ),
        (tr("Отчёт", "Report"), "anomalies.json", BLUE_L, BLUE),
    ]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, top_y, bw, bh, title, sub, fill, edge)
        if index < len(items) - 1:
            arrow(c, x + bw + 2, top_y + bh / 2, x + bw + gap - 2, top_y + bh / 2)
    node(
        c, 0, 5, bw, bh, tr("Эталон", "Answer key"), "ground_truth.json", AMBER_L, AMBER
    )
    node(
        c,
        bw + gap,
        5,
        bw,
        bh,
        tr("Offline-оценка", "Offline evaluation"),
        tr("покрытие A01–A05", "A01–A05 coverage"),
        GREEN_L,
        GREEN,
    )
    arrow(c, bw + 2, 5 + bh / 2, bw + gap - 2, 5 + bh / 2, AMBER)
    poly_arrow(
        c,
        [
            (2 * (bw + gap) + bw / 2, top_y - 2),
            (2 * (bw + gap) + bw / 2, 5 + bh / 2),
            (2 * bw + gap + 2, 5 + bh / 2),
        ],
        BLUE,
    )


def roadmap(c, w, h):
    """Десять этапов курса: выполненные зелёные, следующий синий."""
    titles = [
        tr("Подготовка проекта", "Project setup"),
        tr("PostgreSQL и схема БД", "PostgreSQL and schema"),
        tr("Генерация данных", "Data generation"),
        tr("Аналитическое ядро", "Analytics core"),
        tr("Поиск аномалий", "Anomaly detection"),
        tr("REST API", "REST API"),
        tr("AI-агент", "AI agent"),
        tr("Интерфейс и отчёты", "UI and reports"),
        tr("Тесты и безопасность", "Tests and security"),
        tr("Docker и публикация", "Docker and release"),
    ]
    gap, bh, row_gap = 9, 50, 12
    bw = (w - 4 * gap) / 5
    for index, title in enumerate(titles):
        row, column = divmod(index, 5)
        x = column * (bw + gap)
        y = h - bh - row * (bh + row_gap)
        if index < STAGES_DONE:
            fill, edge, color, status = GREEN_L, GREEN, GREEN, tr("готово", "done")
        elif index == STAGES_DONE:
            fill, edge, color, status = BLUE_L, BLUE, BLUE, tr("далее", "next")
        else:
            fill, edge, color, status = SOFT, LINE, MUTED, ""
        rbox(c, x, y, bw, bh, fill, edge, r=7, lw=1)
        circle_num(c, x + 13, y + bh - 13, 8, str(index + 1), color, WHITE, 8.5)
        if status:
            width = pdfmetrics.stringWidth(status, "PT-Bold", 7.4) + 8
            chip(
                c, x + bw - width - 5, y + bh - 19, status, color, WHITE, "PT-Bold", 7.4
            )
        lines_in(
            c,
            x + bw / 2,
            y + bh - 25,
            bw - 10,
            title,
            "PT-Bold",
            8.6,
            10.2,
            INK if status else MUTED,
        )


def request_flow(c, w, h):
    """Путь HTTP-запроса от клиента до JSON-ответа и место TestClient."""
    gap, bh = 16, 66
    bw = (w - 4 * gap) / 5
    y0 = h - 40 - bh
    items = [
        (
            tr("Клиент", "Client"),
            tr("браузер, curl\nили Swagger /docs", "browser, curl\nor Swagger /docs"),
            ORANGE_L,
            ORANGE,
        ),
        (
            "Uvicorn",
            tr("слушает\n127.0.0.1:8000", "listens on\n127.0.0.1:8000"),
            TEAL_L,
            TEAL,
        ),
        (
            "FastAPI",
            tr("ищет маршрут\nGET /health", "finds the route\nGET /health"),
            BLUE_L,
            BLUE,
        ),
        (
            "health()",
            tr("возвращает\nHealthResponse", "returns\nHealthResponse"),
            VIOLET_L,
            VIOLET,
        ),
        (
            "Pydantic",
            tr(
                "проверяет схему\nи пишет JSON", "validates the schema\nand writes JSON"
            ),
            GREEN_L,
            GREEN,
        ),
    ]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, y0, bw, bh, title, sub, fill, edge)
        circle_num(c, x + 10, y0 + bh - 10, 7, str(index + 1), edge, WHITE, 8)
        if index < len(items) - 1:
            arrow(c, x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2)
    # Ответ возвращается клиенту поверх схемы.
    last_x = 4 * (bw + gap) + bw / 2
    top_y = y0 + bh + 20
    poly_arrow(
        c,
        [
            (last_x, y0 + bh + 2),
            (last_x, top_y),
            (bw / 2, top_y),
            (bw / 2, y0 + bh + 3),
        ],
        GREEN,
    )
    c.setFillColor(GREEN)
    c.setFont("PT", 8.2)
    c.drawCentredString(
        w / 2,
        top_y + 5,
        tr("ответ", "response") + ': HTTP 200 · application/json · {"status":"ok"}',
    )
    # TestClient входит сразу в FastAPI, минуя сеть и Uvicorn.
    fx = 2 * (bw + gap) + bw / 2
    node(
        c,
        fx - 95,
        4,
        190,
        42,
        tr("TestClient в тестах", "TestClient in tests"),
        tr(
            "вызывает приложение напрямую:\nбез сети и без Uvicorn",
            "calls the app directly:\nno network, no Uvicorn",
        ),
        AMBER_L,
        AMBER,
        dash=[3, 2],
    )
    arrow(c, fx, 47, fx, y0 - 2, AMBER, dash=[3, 2])


def uv_flow(c, w, h):
    """Как uv превращает требования в окружение и запускает команды."""
    gap, bh = 46, 70
    bw = (w - 3 * gap) / 4
    y = h - bh - 2
    items = [
        (
            "pyproject.toml",
            tr(
                "что нужно проекту:\nfastapi>=0.142.2",
                "what the project needs:\nfastapi>=0.142.2",
            ),
            BLUE_L,
            BLUE,
        ),
        (
            "uv.lock",
            tr(
                "точные версии и хэши\nвсех пакетов",
                "exact versions and\nhashes of all packages",
            ),
            VIOLET_L,
            VIOLET,
        ),
        (
            ".venv",
            tr(
                "Python 3.12.15\nи установленные пакеты",
                "Python 3.12.15\nand installed packages",
            ),
            TEAL_L,
            TEAL,
        ),
        ("uv run …", "uvicorn, pytest,\nruff, mypy, alembic", GREEN_L, GREEN),
    ]
    commands = [("uv lock", "uv add"), ("uv sync", "--locked"), ("uv run", "")]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, y, bw, bh, title, sub, fill, edge)
        if index < len(items) - 1:
            mid = y + bh / 2
            arrow(c, x + bw + 3, mid, x + bw + gap - 3, mid)
            first, second = commands[index]
            c.setFillColor(INK)
            draw_text(c, x + bw + gap / 2, mid + 6, first, "Mono-Bold", 7.4, "center")
            if second:
                c.setFillColor(MUTED)
                draw_text(c, x + bw + gap / 2, mid - 12, second, "Mono", 7.2, "center")
    # Что хранится в Git, а что пересоздаётся.
    in_git, not_in_git = tr("в Git", "in Git"), tr("не в Git", "not in Git")
    labels = [(in_git, GREEN), (in_git, GREEN), (not_in_git, ORANGE), ("", None)]
    for index, (label, color) in enumerate(labels):
        if label:
            width = pdfmetrics.stringWidth(label, "PT-Bold", 7.6) + 8
            x = index * (bw + gap) + bw / 2 - width / 2
            chip(c, x, y - 20, label, color, WHITE, "PT-Bold", 7.6)


def import_paths(c, w, h):
    """Какие папки видит Python при запуске Uvicorn и pytest."""
    gap = 12
    cw = (w - 2 * gap) / 3
    found = tr("import app: найден", "import app: found")
    columns = [
        (
            "uv run uvicorn app.main:app",
            tr("Uvicorn добавляет текущую папку", "Uvicorn adds the current folder"),
            [
                (tr("'' = корень проекта", "'' = project root"), True),
                (".../lib/python3.12", False),
                (".../site-packages", False),
            ],
            (found, GREEN),
        ),
        (
            "uv run pytest",
            tr("без настройки pythonpath", "without pythonpath"),
            [
                (tr("tests/  (папка теста)", "tests/  (test folder)"), False),
                (".venv/bin", False),
                (".../lib/python3.12", False),
                (".../site-packages", False),
            ],
            ("ModuleNotFoundError", ORANGE),
        ),
        (
            "uv run pytest",
            tr('с pythonpath = ["."]', 'with pythonpath = ["."]'),
            [
                (tr("корень проекта ← pythonpath", "project root ← pythonpath"), True),
                ("tests/", False),
                (".venv/bin", False),
                ("stdlib, site-packages", False),
            ],
            (found, GREEN),
        ),
    ]
    for index, (title, sub, entries, (result, color)) in enumerate(columns):
        x = index * (cw + gap)
        rbox(c, x, 0, cw, h, SOFT, LINE, r=8, lw=0.8)
        c.setFillColor(INK)
        draw_text(c, x + cw / 2, h - 18, title, "Mono-Bold", 7.8, "center")
        c.setFillColor(MUTED)
        draw_text(c, x + cw / 2, h - 31, sub, "PT", 8.4, "center")
        draw_text(c, x + 10, h - 50, "sys.path:", "PT-Bold", 7.8)
        y = h - 74
        for text, is_root in entries:
            fill, edge = (GREEN_L, GREEN) if is_root else (WHITE, LINE)
            rbox(c, x + 8, y, cw - 16, 18, fill, edge, r=4, lw=0.7)
            c.setFillColor(INK)
            draw_text(c, x + 14, y + 6, text, "Mono", 7.6)
            y -= 22
        width = pdfmetrics.stringWidth(result, "PT-Bold", 8.4) + 12
        chip(c, x + (cw - width) / 2, 10, result, color, WHITE, "PT-Bold", 8.4, 6, 17)


def http_anatomy(c, w, h):
    """Из чего состоят HTTP-запрос и HTTP-ответ."""
    gap = 40
    pw = (w - gap) / 2
    body = tr("тело", "body")
    headers = tr("заголовки", "headers")
    panels = [
        (
            tr("Запрос клиента", "Client request"),
            BLUE,
            [
                (tr("строка запроса", "request line"), "GET /health HTTP/1.1"),
                (headers, "host: 127.0.0.1:8000"),
                ("", "accept: */*"),
                (body, tr("нет: GET только читает", "none: GET only reads")),
            ],
        ),
        (
            tr("Ответ сервера", "Server response"),
            GREEN,
            [
                (tr("строка статуса", "status line"), "HTTP/1.1 200 OK"),
                (headers, "content-type: application/json"),
                ("", "content-length: 15"),
                (body, '{"status":"ok"}'),
            ],
        ),
    ]
    for index, (title, color, rows) in enumerate(panels):
        x = index * (pw + gap)
        rbox(c, x, 0, pw, h, WHITE, color, r=8, lw=1.1)
        rbox(c, x, h - 24, pw, 24, color, None, r=8)
        # Прямоугольник того же цвета убирает нижнее скругление шапки панели.
        c.setFillColor(color)
        c.rect(x, h - 24, pw, 10, stroke=0, fill=1)
        c.setFillColor(WHITE)
        draw_text(c, x + 10, h - 16, title, "PT-Bold", 10)
        y = h - 46
        for tag, value in rows:
            c.setFillColor(MUTED)
            draw_text(c, x + 10, y, tag, "PT", 7.8)
            c.setFillColor(INK)
            # Отсутствующее тело запроса - пояснение, а не данные: курсивом.
            font = "PT-Italic" if tag == body and index == 0 else "Mono"
            draw_text(c, x + 74, y, value, font, 7.8)
            y -= 20
    mid_x = pw + gap / 2
    arrow(c, mid_x - 14, h / 2 + 12, mid_x + 14, h / 2 + 12, BLUE)
    arrow(c, mid_x + 14, h / 2 - 12, mid_x - 14, h / 2 - 12, GREEN)


def validation_levels(c, w, h):
    """Эксперимент: неправильный ответ ловят mypy и Pydantic."""
    gap, bh = 18, h - 4
    bw = (w - 3 * gap) / 4
    items = [
        (
            tr("Ошибка в коде", "Bug in the code"),
            tr(
                'health() возвращает\n{"status": "fail"}',
                'health() returns\n{"status": "fail"}',
            ),
            ORANGE_L,
            ORANGE,
        ),
        (
            tr("mypy: до запуска", "mypy: before running"),
            "Incompatible return\nvalue type",
            VIOLET_L,
            VIOLET,
        ),
        (
            tr("FastAPI: при запросе", "FastAPI: on request"),
            "ResponseValidationError:\nInput should be 'ok'",
            BLUE_L,
            BLUE,
        ),
        (
            tr("Клиент", "Client"),
            tr(
                "500 Internal Server Error\nвместо неверных данных",
                "500 Internal Server Error\ninstead of wrong data",
            ),
            AMBER_L,
            AMBER,
        ),
    ]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, 2, bw, bh, title, sub, fill, edge, tsize=9.6, ssize=7.8)
        if index < len(items) - 1:
            arrow(c, x + bw + 2, 2 + bh / 2, x + bw + gap - 2, 2 + bh / 2)


def settings_priority(c, w, h):
    """Откуда Settings берёт значение: окружение важнее .env, .env важнее кода."""
    bar_x, bar_w, bh, gap = 34, 292, 40, 10
    layers = [
        (
            tr("Переменная окружения", "Environment variable"),
            "APP_NAME=... uv run uvicorn ...",
            BLUE_L,
            BLUE,
        ),
        (
            tr("Файл .env", "The .env file"),
            tr('APP_NAME="..."  (файл не в Git)', 'APP_NAME="..."  (not in Git)'),
            TEAL_L,
            TEAL,
        ),
        (
            tr("Значение по умолчанию", "Default value"),
            'app_name = "AI Data Analyst"',
            SLATE_L,
            MUTED,
        ),
    ]
    tops = []
    for index, (title, sub, fill, edge) in enumerate(layers):
        y = h - (index + 1) * bh - index * gap
        tops.append(y)
        rbox(c, bar_x, y, bar_w, bh, fill, edge, r=7, lw=1)
        circle_num(c, bar_x + 16, y + bh / 2, 9, str(index + 1), edge, WHITE, 9)
        c.setFillColor(INK)
        draw_text(c, bar_x + 34, y + bh - 16, title, "PT-Bold", 9.6)
        c.setFillColor(MUTED)
        draw_text(c, bar_x + 34, y + 8, sub, "Mono", 7.6)
    # Вертикальная стрелка приоритета слева.
    arrow(c, 12, tops[2] + 6, 12, tops[0] + bh - 4, MUTED, 1.2)
    c.saveState()
    c.translate(6, (tops[2] + tops[0] + bh) / 2)
    c.rotate(90)
    c.setFillColor(MUTED)
    c.setFont("PT", 7.8)
    c.drawCentredString(0, 0, tr("важнее", "wins"))
    c.restoreState()
    # Итоговое значение справа.
    rx = bar_x + bar_w + 40
    rw = w - rx
    ry = tops[1] - 6
    node(
        c,
        rx,
        ry,
        rw,
        bh + 12,
        "get_settings().app_name",
        tr(
            "первый источник, где\nзначение задано",
            "the first source\nthat sets a value",
        ),
        GREEN_L,
        GREEN,
        tsize=8.8,
    )
    for index, top in enumerate(tops):
        dash = None if index == 0 else [3, 2]
        arrow(
            c,
            bar_x + bar_w + 3,
            top + bh / 2,
            rx - 3,
            ry + (bh + 12) / 2,
            GREEN if index == 0 else MUTED,
            1.1,
            5,
            dash,
        )


def fixture_flow(c, w, h):
    """Жизненный цикл фикстуры client вокруг одного теста."""
    gap, bh = 20, h - 4
    bw = (w - 3 * gap) / 4
    items = [
        (
            tr("pytest находит тест", "pytest finds a test"),
            "test_health_returns_ok\n(client: TestClient)",
            SLATE_L,
            MUTED,
        ),
        (
            tr("Код до yield", "Code before yield"),
            tr(
                "with TestClient(app)\nоткрывает клиент",
                "with TestClient(app)\nopens the client",
            ),
            TEAL_L,
            TEAL,
        ),
        (
            tr("Сам тест", "The test itself"),
            tr(
                "client.get('/health')\nи проверки assert",
                "client.get('/health')\nand assert checks",
            ),
            BLUE_L,
            BLUE,
        ),
        (
            tr("Код после yield", "Code after yield"),
            tr(
                "with закрывает клиент,\nдаже если тест упал",
                "with closes the client,\neven if the test failed",
            ),
            GREEN_L,
            GREEN,
        ),
    ]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, 2, bw, bh, title, sub, fill, edge, tsize=9.6, ssize=7.8)
        circle_num(c, x + 10, 2 + bh - 10, 7, str(index + 1), edge, WHITE, 8)
        if index < len(items) - 1:
            arrow(c, x + bw + 2, 2 + bh / 2, x + bw + gap - 2, 2 + bh / 2)


def git_flow(c, w, h):
    """Путь изменения от рабочей папки до GitHub и запуска Actions."""
    gap, bh = 58, h - 4
    bw = (w - 3 * gap) / 4
    items = [
        (
            tr("Рабочая папка", "Working folder"),
            tr("файлы, которые\nты изменил", "files you\nhave changed"),
            SLATE_L,
            MUTED,
        ),
        (
            tr("Индекс", "Index"),
            tr("что войдёт\nв следующий коммит", "what goes into\nthe next commit"),
            BLUE_L,
            BLUE,
        ),
        (
            tr("Локальная история", "Local history"),
            tr("коммиты в папке .git\nна твоём Mac", "commits in .git\non your Mac"),
            VIOLET_L,
            VIOLET,
        ),
        (
            "GitHub",
            tr("origin/main;\npush запускает CI", "origin/main;\npush triggers CI"),
            GREEN_L,
            GREEN,
        ),
    ]
    commands = ["git add", "git commit", "git push"]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, 2, bw, bh, title, sub, fill, edge, tsize=9.6, ssize=7.8)
        if index < len(items) - 1:
            mid = 2 + bh / 2
            arrow(c, x + bw + 3, mid, x + bw + gap - 3, mid)
            c.setFillColor(INK)
            draw_text(
                c,
                x + bw + gap / 2,
                mid + 6,
                commands[index],
                "Mono-Bold",
                7.2,
                "center",
            )


def compose_services(c, w, h):
    """Процессы на Mac и два контейнера PostgreSQL из compose.yaml."""
    panel_x = 232
    rbox(c, panel_x, 0, w - panel_x, h, SOFT, LINE, r=8, lw=0.8, dash=[4, 3])
    c.setFillColor(MUTED)
    draw_text(c, panel_x + 10, h - 15, "Docker Desktop · compose.yaml", "PT-Bold", 8.4)
    host_w, box_h = 168, 58
    cont_x, cont_w = panel_x + 14, 120
    store_x = cont_x + cont_w + 12
    store_w = w - store_x - 10
    rows = [
        (
            h - 32 - box_h,
            (
                tr("API, Alembic, учебный набор", "API, Alembic, sample data"),
                "uvicorn · alembic · python -m app.db.sample",
                BLUE_L,
                BLUE,
            ),
            ("127.0.0.1:5436", "DATABASE_URL"),
            ("db", "postgres:17\nindustrialflow", TEAL_L, TEAL),
            (
                tr("том postgres_data", "volume postgres_data"),
                tr("переживает\ndocker compose down", "survives\ndocker compose down"),
                GREEN_L,
                GREEN,
            ),
        ),
        (
            10,
            (
                tr("Интеграционные тесты", "Integration tests"),
                "pytest tests/integration",
                VIOLET_L,
                VIOLET,
            ),
            ("127.0.0.1:5437", "TEST_DATABASE_URL"),
            ("db-test", "profile test\nindustrialflow_test", AMBER_L, AMBER),
            (
                "tmpfs",
                tr(
                    "в памяти: исчезает\nпри остановке", "in memory: gone\nwhen stopped"
                ),
                SLATE_L,
                MUTED,
            ),
        ),
    ]
    for y, host, (port, variable), container, storage in rows:
        node(
            c,
            0,
            y,
            host_w,
            box_h,
            host[0],
            host[1],
            host[2],
            host[3],
            tsize=9.4,
            ssize=7.4,
            sub_font="Mono",
        )
        mid = y + box_h / 2
        arrow(c, host_w + 3, mid, cont_x - 3, mid, INK, 1.2)
        c.setFillColor(INK)
        draw_text(c, (host_w + cont_x) / 2, mid + 5, port, "Mono-Bold", 6.8, "center")
        c.setFillColor(MUTED)
        draw_text(c, (host_w + cont_x) / 2, mid - 11, variable, "Mono", 6.4, "center")
        node(
            c,
            cont_x,
            y,
            cont_w,
            box_h,
            container[0],
            container[1],
            container[2],
            container[3],
            tsize=9.6,
            ssize=7.4,
        )
        c.saveState()
        c.setStrokeColor(MUTED)
        c.setLineWidth(1.2)
        c.line(cont_x + cont_w, mid, store_x, mid)
        c.restoreState()
        node(
            c,
            store_x,
            y,
            store_w,
            box_h,
            storage[0],
            storage[1],
            storage[2],
            storage[3],
            tsize=8.8,
            ssize=7.2,
        )


# Столбцы таблиц для ER-схемы: (имя, пометка ключа).
ER_TABLES = {
    "customers": [("id", "PK"), ("name", ""), ("region", ""), ("industry", "")],
    "orders": [
        ("id", "PK"),
        ("customer_id", "FK"),
        ("status", ""),
        ("ordered_at", ""),
        ("paid_at", ""),
    ],
    "order_items": [
        ("id", "PK"),
        ("order_id", "FK"),
        ("product_id", "FK"),
        ("quantity", ""),
        ("unit_price", ""),
        ("discount", ""),
    ],
    "inventory_snapshots": [
        ("id", "PK"),
        ("product_id", "FK"),
        ("snapshot_date", ""),
        ("quantity", ""),
    ],
    "products": [
        ("id", "PK"),
        ("sku", "UQ"),
        ("name", ""),
        ("category", ""),
        ("cost", ""),
    ],
    "refunds": [
        ("id", "PK"),
        ("order_item_id", "FK"),
        ("amount", ""),
        ("processed_at", ""),
    ],
}


def er_table(c, x, top, width, name, color, fill):
    """Нарисовать таблицу ER-схемы сверху вниз; вернуть (низ, высота)."""
    columns = ER_TABLES[name]
    row_h, head_h = 11.5, 17
    height = head_h + len(columns) * row_h + 6
    y = top - height
    rbox(c, x, y, width, height, fill, color, r=6, lw=1)
    rbox(c, x, top - head_h, width, head_h, color, None, r=6)
    c.setFillColor(color)
    c.rect(x, top - head_h, width, 6, stroke=0, fill=1)
    c.setFillColor(WHITE)
    draw_text(c, x + 8, top - 12, name, "Mono-Bold", 8)
    row_y = top - head_h - 10
    for column, mark in columns:
        c.setFillColor(INK)
        draw_text(c, x + 8, row_y, column, "Mono", 7.4)
        if mark:
            c.setFillColor(color)
            draw_text(c, x + width - 8, row_y, mark, "Mono-Bold", 6.8, "right")
        row_y -= row_h
    return y, height


def relation(c, points, one_at, many_at, color=MUTED):
    """Линия связи «один ко многим» с подписями 1 и N у концов."""
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(1.1)
    for (ax, ay), (bx, by) in zip(points[:-1], points[1:], strict=True):
        c.line(ax, ay, bx, by)
    c.setFillColor(color)
    c.setFont("PT-Bold", 8)
    c.drawString(one_at[0], one_at[1], "1")
    c.drawString(many_at[0], many_at[1], "N")
    c.restoreState()


def er_diagram(c, w, h):
    """Шесть таблиц и связи «один ко многим» между ними."""
    width = 146
    gap = (w - 3 * width) / 2
    xs = [0, width + gap, 2 * (width + gap)]
    top = h - 2
    er_table(c, xs[0], top, width, "customers", ORANGE, ORANGE_L)
    y_orders, _ = er_table(c, xs[1], top, width, "orders", BLUE, BLUE_L)
    y_items, _ = er_table(c, xs[2], top, width, "order_items", VIOLET, VIOLET_L)
    bottom_top = 104
    er_table(c, xs[0], bottom_top, width, "inventory_snapshots", MUTED, SLATE_L)
    er_table(c, xs[1], bottom_top, width, "products", TEAL, TEAL_L)
    er_table(c, xs[2], bottom_top, width, "refunds", GREEN, GREEN_L)
    head_mid = top - 30
    # customers 1 — N orders, orders 1 — N order_items.
    relation(
        c,
        [(xs[0] + width, head_mid), (xs[1], head_mid)],
        (xs[0] + width + 3, head_mid + 3),
        (xs[1] - 10, head_mid + 3),
    )
    relation(
        c,
        [(xs[1] + width, head_mid), (xs[2], head_mid)],
        (xs[1] + width + 3, head_mid + 3),
        (xs[2] - 10, head_mid + 3),
    )
    # order_items 1 — N refunds.
    rx = xs[2] + width - 30
    relation(
        c,
        [(rx, y_items), (rx, bottom_top)],
        (rx + 4, y_items - 12),
        (rx + 4, bottom_top + 4),
    )
    # products 1 — N order_items: вверх, вправо и снова вверх.
    px = xs[1] + width / 2
    mid_y = (y_items + bottom_top) / 2
    ix = xs[2] + 30
    relation(
        c,
        [(px, bottom_top), (px, mid_y), (ix, mid_y), (ix, y_items)],
        (px + 4, bottom_top + 4),
        (ix + 4, y_items - 12),
    )
    # products 1 — N inventory_snapshots.
    pm = bottom_top - 30
    relation(
        c,
        [(xs[1], pm), (xs[0] + width, pm)],
        (xs[1] - 9, pm + 3),
        (xs[0] + width + 3, pm + 3),
    )
    c.setFillColor(MUTED)
    c.setFont("PT", 7.6)
    c.drawString(
        xs[0],
        3,
        tr(
            "PK — первичный ключ, FK — внешний ключ, UQ — уникальное значение",
            "PK primary key, FK foreign key, UQ unique value",
        ),
    )


def migration_flow(c, w, h):
    """Модели → файл миграции → база; check сравнивает модели и базу."""
    gap, bh = 76, 66
    bw = (w - 2 * gap) / 3
    y = h - bh - 2
    items = [
        (
            "app/db/models.py",
            tr("какой схема\nдолжна быть", "what the schema\nshould be"),
            BLUE_L,
            BLUE,
        ),
        (
            "0001_initial_schema.py",
            tr(
                "черновик Alembic,\nпрочитанный глазами",
                "Alembic draft,\nreviewed by a human",
            ),
            VIOLET_L,
            VIOLET,
        ),
        (
            "PostgreSQL",
            tr(
                "6 таблиц +\nalembic_version = 0001",
                "6 tables +\nalembic_version = 0001",
            ),
            TEAL_L,
            TEAL,
        ),
    ]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, y, bw, bh, title, sub, fill, edge, tsize=8.8, ssize=7.8)
    mid = y + bh / 2
    labels = [("revision", "--autogenerate"), ("upgrade", "head")]
    for index, (first, second) in enumerate(labels):
        x = index * (bw + gap) + bw
        arrow(c, x + 3, mid, x + gap - 3, mid, INK, 1.2)
        c.setFillColor(INK)
        draw_text(c, x + gap / 2, mid + 6, first, "Mono-Bold", 7.2, "center")
        c.setFillColor(MUTED)
        draw_text(c, x + gap / 2, mid - 12, second, "Mono", 7, "center")
    file_x = bw + gap + bw / 2
    db_x = 2 * (bw + gap) + bw / 2
    # Откат: из базы обратно к файлу миграции.
    down_y = y - 22
    poly_arrow(
        c,
        [
            (db_x + 20, y - 2),
            (db_x + 20, down_y),
            (file_x + 20, down_y),
            (file_x + 20, y - 3),
        ],
        ORANGE,
        1.1,
        5,
        [3, 2],
    )
    c.setFillColor(ORANGE)
    draw_text(
        c, (db_x + file_x) / 2 + 20, down_y + 4, "downgrade base", "Mono", 7.2, "center"
    )
    # alembic check: сравнение моделей с базой.
    check_y = 12
    models_x = bw / 2
    c.saveState()
    c.setStrokeColor(GREEN)
    c.setLineWidth(1.1)
    c.line(models_x, y - 2, models_x, check_y)
    c.line(models_x, check_y, db_x - 20, check_y)
    c.line(db_x - 20, check_y, db_x - 20, y - 2)
    c.restoreState()
    c.setFillColor(GREEN)
    draw_text(
        c,
        (models_x + db_x - 20) / 2,
        check_y + 5,
        "alembic check: No new upgrade operations detected.",
        "Mono",
        7.2,
        "center",
    )


def ready_flow(c, w, h):
    """Как /ready решает, отвечать 200 или 503."""
    gap, bh = 14, 62
    bw = (w - 4 * gap) / 5
    y = h - bh - 2
    items = [
        (
            "GET /ready",
            tr("запрос проверки\nготовности", "readiness\nrequest"),
            SLATE_L,
            MUTED,
        ),
        (
            "database_engine()",
            tr(
                "пул соединений;\nнет DATABASE_URL", "connection pool;\nno DATABASE_URL"
            ),
            BLUE_L,
            BLUE,
        ),
        (
            "alembic_version",
            tr("соединиться и\nпрочитать версию", "connect and\nread the version"),
            VIOLET_L,
            VIOLET,
        ),
        (
            "expected_revision()",
            tr(
                "сравнить с head\nиз migrations/", "compare with head\nfrom migrations/"
            ),
            TEAL_L,
            TEAL,
        ),
        (
            "200 OK",
            tr("ready,\nrevision 0001", "ready,\nrevision 0001"),
            GREEN_L,
            GREEN,
        ),
    ]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        font = "PT"
        node(
            c, x, y, bw, bh, title, sub, fill, edge, tsize=8.4, ssize=7.2, sub_font=font
        )
        if index < len(items) - 1:
            arrow(c, x + bw + 2, y + bh / 2, x + bw + gap - 2, y + bh / 2)
    fail_x = bw + gap
    fail_w = 3 * bw + 2 * gap
    node(
        c,
        fail_x,
        4,
        fail_w,
        30,
        '503 · {"detail": "Database is not ready"}',
        tr(
            "не настроена · недоступна · пустая или устаревшая схема",
            "not configured · unreachable · empty or outdated schema",
        ),
        ORANGE_L,
        ORANGE,
        tsize=8.4,
        ssize=7.4,
    )
    for index in (1, 2, 3):
        x = index * (bw + gap) + bw / 2
        arrow(c, x, y - 2, x, 36, ORANGE, 1, 4.5, [3, 2])


def timezone_timeline(c, w, h):
    """Один момент оплаты в UTC и по Москве: граница месяца разная."""
    label_w = 92
    x0, x1 = label_w, w - 4
    hours = 6  # ось: 30 сентября 20:00 UTC … 1 октября 02:00 UTC

    def x_at(hours_from_start):
        """Координата x момента: часы от 30.09 20:00 UTC."""
        return x0 + (x1 - x0) * hours_from_start / hours

    lane_h = 34
    lanes = [
        ("UTC", h - 18 - lane_h, 4, "30.09 22:30"),
        (tr("Москва, UTC+3", "Moscow, UTC+3"), 26, 1, "01.10 01:30"),
    ]
    for title, y, boundary, local in lanes:
        c.setFillColor(INK)
        draw_text(c, 0, y + lane_h / 2 - 3, title, "PT-Bold", 9)
        bx = x_at(boundary)
        rbox(c, x0, y, bx - x0, lane_h, BLUE_L, None, r=3)
        rbox(c, bx, y, x1 - bx, lane_h, AMBER_L, None, r=3)
        c.setFillColor(BLUE)
        draw_text(
            c,
            (x0 + bx) / 2,
            y + lane_h / 2 - 3,
            tr("сентябрь", "September"),
            "PT-Bold",
            8.4,
            "center",
        )
        c.setFillColor(AMBER)
        draw_text(
            c,
            (bx + x1) / 2 + 30,
            y + lane_h / 2 - 3,
            tr("октябрь", "October"),
            "PT-Bold",
            8.4,
            "center",
        )
        c.saveState()
        c.setStrokeColor(ORANGE)
        c.setLineWidth(1.4)
        c.line(bx, y - 4, bx, y + lane_h + 4)
        c.restoreState()
        c.setFillColor(ORANGE)
        draw_text(
            c,
            bx,
            y + lane_h + 6,
            tr("граница месяца", "month boundary"),
            "PT",
            7.2,
            "center",
        )
        c.setFillColor(INK)
        draw_text(c, x_at(2.5) + 6, y + 5, local, "Mono-Bold", 7.6)
    # Момент оплаты заказа №5: одна вертикаль через обе дорожки.
    px = x_at(2.5)
    c.saveState()
    c.setStrokeColor(INK)
    c.setLineWidth(1.6)
    c.line(px, 18, px, h - 12)
    c.setFillColor(INK)
    for y in (h - 18 - lane_h / 2, 26 + lane_h / 2):
        c.circle(px, y, 3.2, stroke=0, fill=1)
    c.restoreState()
    c.setFillColor(INK)
    draw_text(
        c,
        px,
        6,
        tr(
            "оплата заказа №5 — один и тот же момент",
            "payment of order 5 — the same moment",
        ),
        "PT-Bold",
        8,
        "center",
    )


def mini_table(c, x, top, width, title, rows, color, fill, highlight=None):
    """Небольшая таблица строк с заголовком; вернуть y центров строк."""
    row_h, head_h = 18, 18
    height = head_h + len(rows) * row_h
    rbox(c, x, top - height, width, height, fill, color, r=5, lw=1)
    rbox(c, x, top - head_h, width, head_h, color, None, r=5)
    c.setFillColor(color)
    c.rect(x, top - head_h, width, 6, stroke=0, fill=1)
    c.setFillColor(WHITE)
    draw_text(c, x + 7, top - 12.5, title, "Mono-Bold", 7.8)
    centers = []
    y = top - head_h - row_h
    for index, text in enumerate(rows):
        if highlight and index in highlight:
            rbox(c, x + 3, y + 2, width - 6, row_h - 4, ORANGE_L, None, r=3)
        c.setFillColor(INK)
        draw_text(c, x + 7, y + 6, text, "Mono", 7.6)
        centers.append(y + row_h / 2)
        y -= row_h
    return centers


def double_count(c, w, h):
    """JOIN позиции с двумя возвратами повторяет её сумму дважды."""
    left_w, join_x = 160, 250
    top = h - 4
    item_rows = mini_table(
        c,
        0,
        top,
        left_w,
        "order_items",
        [tr("5 датчиков   10 000.00", "5 sensors   10 000.00")],
        VIOLET,
        VIOLET_L,
    )
    refund_rows = mini_table(
        c, 0, top - 46, left_w, "refunds", ["1 000.00", "500.00"], GREEN, GREEN_L
    )
    join_rows = mini_table(
        c,
        join_x,
        top,
        w - join_x,
        "order_items JOIN refunds",
        ["10 000.00 | 1 000.00", "10 000.00 |   500.00"],
        ORANGE,
        ORANGE_L,
        highlight={1},
    )
    # Позиция попадает в обе строки результата, каждый возврат — в одну.
    for target in join_rows:
        arrow(c, left_w + 3, item_rows[0], join_x - 3, target, VIOLET, 1, 4.5, [3, 2])
    for source, target in zip(refund_rows, join_rows, strict=True):
        arrow(c, left_w + 3, source, join_x - 3, target, GREEN, 1, 4.5)
    lines_in(
        c,
        join_x + (w - join_x) / 2,
        top - 64,
        w - join_x - 10,
        tr(
            "SUM(line_total) = 20 000.00 вместо 10 000.00",
            "SUM(line_total) = 20 000.00 instead of 10 000.00",
        ),
        "PT-Bold",
        8.4,
        10.5,
        ORANGE,
    )


def integration_fixtures(c, w, h):
    """Цепочка фикстур интеграционных тестов."""
    gap, bh = 14, h - 4
    bw = (w - 4 * gap) / 5
    items = [
        (
            "TEST_DATABASE_URL",
            tr(
                "только база *_test;\nбез адреса: skip / в CI ошибка",
                "*_test database only;\nmissing: skip / CI fails",
            ),
            SLATE_L,
            MUTED,
        ),
        (
            "migrated_engine",
            tr(
                "один раз за прогон:\ndowngrade base →\nupgrade head",
                "once per run:\ndowngrade base →\nupgrade head",
            ),
            BLUE_L,
            BLUE,
        ),
        (
            "db_session",
            tr("транзакция\nна каждый тест", "a transaction\nper test"),
            VIOLET_L,
            VIOLET,
        ),
        (
            tr("тест", "test"),
            tr(
                "вставки, запросы,\nожидаемые ошибки",
                "inserts, queries,\nexpected errors",
            ),
            TEAL_L,
            TEAL,
        ),
        (
            "rollback",
            tr("данные теста\nисчезают", "the test's rows\ndisappear"),
            GREEN_L,
            GREEN,
        ),
    ]
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, 2, bw, bh, title, sub, fill, edge, tsize=8.4, ssize=7.2)
        circle_num(c, x + 9, 2 + bh - 9, 6.5, str(index + 1), edge, WHITE, 7.5)
        if index < len(items) - 1:
            arrow(c, x + bw + 2, 2 + bh / 2, x + bw + gap - 2, 2 + bh / 2)


def ci_pipeline(c, w, h):
    """Задание CI: события, сервис PostgreSQL и десять шагов по порядку."""
    c.setFillColor(INK)
    draw_text(c, 0, h - 11, tr("Запуск:", "Runs on:"), "PT-Bold", 9)
    x = 52
    for label in (
        tr("push в main", "push to main"),
        tr("pull request в main", "pull request to main"),
        tr("вручную: workflow_dispatch", "manual: workflow_dispatch"),
    ):
        x += chip(c, x, h - 15, label, ORANGE_L, ORANGE, "PT-Bold", 7.8, 6, 15) + 6
    panel_top = h - 26
    rbox(c, 0, 0, w, panel_top, SOFT, LINE, r=8, lw=0.8)
    c.setFillColor(MUTED)
    draw_text(
        c,
        10,
        panel_top - 15,
        tr(
            "задание checks · ubuntu-24.04 · не дольше 10 минут",
            "job checks · ubuntu-24.04 · up to 10 minutes",
        ),
        "PT-Bold",
        8.4,
    )
    service = tr(
        "сервис: postgres:17 (digest) · база industrialflow_test",
        "service: postgres:17 (digest) · database industrialflow_test",
    )
    width = pdfmetrics.stringWidth(service, "PT-Bold", 7.6) + 12
    chip(c, w - width - 10, panel_top - 19, service, TEAL, WHITE, "PT-Bold", 7.6, 6, 14)
    gap, bh, row_gap = 14, 40, 18
    bw = (w - 20 - 3 * gap) / 4
    row1 = panel_top - 30 - bh
    rows_y = [row1, row1 - bh - row_gap, row1 - 2 * (bh + row_gap)]
    steps = [
        ("Checkout", tr("код коммита", "commit code"), BLUE_L, BLUE),
        ("uv 0.12.23", tr("и Python 3.12", "and Python 3.12"), BLUE_L, BLUE),
        ("uv sync --locked", "lock = pyproject", BLUE_L, BLUE),
        ("Ruff lint", "ruff check .", VIOLET_L, VIOLET),
        ("Ruff format", "format --check", VIOLET_L, VIOLET),
        ("mypy", "app tests migrations", VIOLET_L, VIOLET),
        ("alembic upgrade", "head", TEAL_L, TEAL),
        ("alembic check", tr("модели = миграции", "models = migrations"), TEAL_L, TEAL),
        ("downgrade base", tr("и снова upgrade", "and upgrade again"), TEAL_L, TEAL),
        (
            "pytest",
            tr("unit + integration, CI=true", "unit + integration, CI=true"),
            GREEN_L,
            GREEN,
        ),
        (
            tr("Итог", "Result"),
            tr("всё PASS:\nзадание зелёное", "all PASS:\njob is green"),
            GREEN_L,
            GREEN,
        ),
    ]
    positions = []
    for index in range(len(steps)):
        row, column = divmod(index, 4)
        # Змейка: вторая строка идёт справа налево.
        if row == 1:
            column = 3 - column
        positions.append((10 + column * (bw + gap), rows_y[row]))
    for index, ((title, sub, fill, edge), (x, y)) in enumerate(
        zip(steps, positions, strict=True)
    ):
        node(c, x, y, bw, bh, title, sub, fill, edge, tsize=8.6, ssize=7.2)
        if index < len(steps) - 1:
            circle_num(c, x + 8, y + bh - 8, 6.2, str(index + 1), edge, WHITE, 7)
    for index in range(len(steps) - 1):
        (ax, ay), (bx, by) = positions[index], positions[index + 1]
        if ay == by and bx > ax:
            arrow(c, ax + bw + 2, ay + bh / 2, bx - 2, by + bh / 2)
        elif ay == by:
            arrow(c, ax - 2, ay + bh / 2, bx + bw + 2, by + bh / 2)
        else:
            arrow(c, ax + bw / 2, ay - 2, bx + bw / 2, by + bh + 2)
