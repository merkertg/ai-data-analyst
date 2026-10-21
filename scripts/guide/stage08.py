"""Bilingual sections 37–39: Streamlit, exact display and report workflows."""

from reportlab.platypus import Spacer

from guide.diagrams import ui_flow
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
    TEAL,
    VIOLET,
    VIOLET_L,
    Diagram,
    W,
    callout,
    code_block,
    mono,
    p,
    simple_table,
)
from guide.toc import number_of, section


def add_stage08(story):
    """Explain the HTTP-only UI, exact values, agent runs and saved snapshots."""
    section(
        story,
        number_of("Интерфейс Streamlit"),
        tr(
            "Браузерный интерфейс над готовым REST API, без второго аналитического ядра.",
            "A browser interface over the existing REST API, using the same analytics core.",
        ),
        BLUE,
    )
    story += [
        p(
            tr(
                "На этапе 08 показатели, вопросы агенту и сохранённые отчёты доступны "
                "в браузере. <b>Streamlit</b> строит страницу из Python-кода в "
                "<b>ui/main.py</b>. Действия пользователя вызывают HTTP-клиент "
                "<b>ui/client.py</b>, который обращается к FastAPI. PostgreSQL и SDK "
                "модели работают на сервере API. Импорт общих схем ответа "
                "подтягивает метаданные моделей, но UI не создаёт сессии "
                "и не открывает соединение с базой.",
                "Stage 08 makes metrics, agent questions and saved reports available "
                "in a browser. <b>Streamlit</b> builds the page from Python code in "
                "<b>ui/main.py</b>. User actions call the HTTP client in "
                "<b>ui/client.py</b>, which talks to FastAPI. PostgreSQL and the model "
                "SDK run on the API server. Importing shared response schemas also "
                "imports model metadata, but the UI creates no database session "
                "and opens no database connection.",
            )
        ),
        Diagram(96, ui_flow),
        p(tr("Запуск в двух терминалах", "Run in two terminals"), H2),
        code_block(
            "uv run uvicorn app.main:app --reload\n"
            "# In another terminal, from the same project root:\n"
            "uv run python -m streamlit run ui/main.py --server.address 127.0.0.1"
        ),
        Spacer(1, 6),
        p(
            tr(
                "Сначала подготовь .env, запусти PostgreSQL, примени миграции "
                "и загрузи demo по предыдущим этапам. Убедись, что "
                "<b>http://127.0.0.1:8000/ready</b> отвечает 200. После запуска "
                "Streamlit открой <b>http://127.0.0.1:8501</b>. Это отдельный "
                "процесс: остановка API оставляет страницу открытой, но новые "
                "запросы покажут ошибку соединения.",
                "First prepare .env, start PostgreSQL, apply migrations and load "
                "the demo as explained in earlier stages. Confirm that "
                "<b>http://127.0.0.1:8000/ready</b> returns 200. After starting "
                "Streamlit, open <b>http://127.0.0.1:8501</b>. It is a separate "
                "process: stopping the API leaves the page open, but new requests "
                "show a connection error.",
            ),
            BODY_S,
        ),
        Spacer(1, 5),
        simple_table(
            [tr("Настройка", "Setting"), tr("Назначение", "Purpose")],
            [
                [
                    mono("UI_API_URL"),
                    tr(
                        "Адрес локального FastAPI, по умолчанию http://127.0.0.1:8000; без пароля и пути.",
                        "Local FastAPI address; http://127.0.0.1:8000 by default, without credentials or a path.",
                    ),
                ],
                [
                    mono("UI_REQUEST_TIMEOUT_SECONDS"),
                    tr(
                        "Ожидание ответа: 150 с по умолчанию, от 1 до 600 с; не отменяет запущенного агента.",
                        "Response timeout: 150 s by default, range 1–600 s; does not cancel an active agent run.",
                    ),
                ],
                [
                    mono("LLM_PROVIDER=mock"),
                    tr(
                        "Настройка API: учебный сценарий без ключа и обращения к OpenAI.",
                        "An API setting: the teaching scenario needs no key or OpenAI request.",
                    ),
                ],
            ],
            [195, W - 195],
            [CELL, CELL],
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Ключ модели вводится на стороне API.</b> Интерфейс не запрашивает "
                "OpenAI API key. Он показывает тот результат, который вернул сервер. "
                "Mock повторяет фиксированный сценарий этапа 07, а не понимает "
                "произвольный диалог. Авторизация и публикация ещё относятся "
                "к следующим этапам; текущий запуск слушает loopback.",
                "<b>The model key belongs on the API side.</b> The interface does not "
                "ask for an OpenAI API key. It displays the server's result. Mock "
                "follows the fixed Stage 07 scenario rather than understanding an "
                "arbitrary conversation. Authentication and release belong to later "
                "stages; the current launch listens on loopback.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    section(
        story,
        number_of("Показатели и графики"),
        tr(
            "Точные подписи и таблицы; приблизительные координаты только для рисования.",
            "Exact labels and tables; approximate coordinates only for drawing.",
        ),
        TEAL,
    )
    story += [
        p(
            tr(
                "В боковом меню выбери <b>Dashboard</b>, затем полуоткрытый период: начало "
                "включается, конец — нет, время Europe/Moscow. Для сентября "
                "это <b>2026-09-01 → 2026-10-01</b>. Сравнение, категории, регионы "
                "и кандидаты на аномалии берутся из маршрутов этапа 06. "
                "Месячные графики показывают выручку и заказы, столбцы категорий "
                "и регионов — вклад в изменение со знаком. Кнопка формы "
                "отправляет параметры; аномалии запрашиваются отдельной формой.",
                "Select <b>Dashboard</b> in the sidebar, then a half-open period: the start is "
                "included and the end excluded, in Europe/Moscow time. September "
                "is <b>2026-09-01 → 2026-10-01</b>. Comparisons, categories, regions "
                "and anomaly candidates come from the Stage 06 routes. A form "
                "button sends the chosen parameters. Monthly charts show revenue "
                "and orders, while category and region bars show signed "
                "contributions to the change. Anomalies use a separate form.",
            )
        ),
        simple_table(
            [
                tr("Слой", "Layer"),
                tr("Как представляет деньги", "Money representation"),
            ],
            [
                [
                    "PostgreSQL / Python",
                    tr(
                        "NUMERIC и Decimal: все суммы, доли и изменения считает сервер.",
                        "NUMERIC and Decimal: the server computes sums, shares and changes.",
                    ),
                ],
                [
                    "JSON / UI",
                    tr(
                        "Десятичная строка; подпись сохраняет копейки, null означает «нет значения».",
                        "A decimal string; the label keeps kopecks and null means unavailable.",
                    ),
                ],
                [
                    "Plotly",
                    tr(
                        "float задаёт высоту точки или столбца; точный текст передаётся отдельно в customdata.",
                        "A float sets a point or bar height; exact text is supplied separately in customdata.",
                    ),
                ],
            ],
            [145, W - 145],
            [CELL, CELL],
        ),
        p(
            tr(
                "Почему у графика два представления числа",
                "Why a chart has two representations",
            ),
            H2,
        ),
        code_block(
            'money = Decimal("466678757.35")\n'
            "y_coordinate = float(money)\n"
            'exact_label = format(money, ",.2f")\n'
            "# Plotly: y=[y_coordinate], customdata=[exact_label]\n"
            "# Hover text uses %{customdata}, not a recalculated total."
        ),
        Spacer(1, 6),
        p(
            tr(
                "Plotly нужен числовой массив, чтобы расположить отметки на оси. "
                "Переход к float нужен только этому рисунку. Итоги из координат "
                "не пересчитываются; карточки, таблицы, всплывающие подсказки "
                "и скачанный JSON сохраняют значения API. Если процент не "
                "определён из-за нулевой базы, UI показывает отсутствие значения, "
                "а не заменяет его нулём.",
                "Plotly needs a numeric array to position marks on an axis. The "
                "conversion to float serves only that drawing. Totals are never "
                "recalculated from coordinates; cards, tables, hover labels and "
                "downloaded JSON retain the API values. If a percentage is "
                "undefined because the baseline is zero, the UI displays an "
                "unavailable value instead of replacing it with zero.",
            ),
            BODY_S,
        ),
        Spacer(1, 8),
        callout(
            tr(
                "<b>Проверка глазами.</b> Сравни одно значение карточки, таблицы "
                "и подсказки графика с GET /api/metrics/revenue в /docs. Затем "
                "выбери период без продаж: интерфейс должен показать пустой "
                "результат без выдуманных чисел. Кандидат на аномалию остаётся "
                "сигналом для проверки, а не доказанной причиной падения.",
                "<b>Visual check.</b> Compare one card, table and chart hover "
                "value with GET /api/metrics/revenue in /docs. Then choose a "
                "period with no sales: the UI should show an empty result "
                "without invented figures. An anomaly candidate remains a signal "
                "to investigate, rather than a proven cause of a decline.",
            ),
            GREEN,
            GREEN_L,
        ),
    ]

    section(
        story,
        number_of("Вопросы и отчёты в UI"),
        tr(
            "Один вопрос — один запуск агента; сохранённая история живёт в API.",
            "One question creates one agent run; saved history lives in the API.",
        ),
        VIOLET,
    )
    story += [
        p(
            tr(
                "Выбери <b>AI analyst</b>. Введи, например, «Почему в сентябре "
                "2026 года снизилась выручка?» "
                "и отправь вопрос. UI делает <b>POST /api/agent/runs</b> и показывает "
                "готовый отчёт: сводку, факты с доказательствами, гипотезы, "
                "рекомендации и ограничения. Это отдельный запуск; внешний вид "
                "чата не добавляет модели память прошлых вопросов. В сохранённой "
                "истории можно открыть предыдущий запуск и увидеть его результат. "
                "Виджеты перезапускают Python-код страницы; session_state хранит "
                "отправленный запрос и ответ, поэтому новый POST требует отправки формы.",
                "Select <b>AI analyst</b>. Enter, for example, “Why did revenue "
                "fall in September 2026?” "
                "and submit the question. The UI sends <b>POST /api/agent/runs</b> "
                "and displays the finished report: a summary, facts with evidence, "
                "hypotheses, recommendations and limitations. Each is a separate "
                "run; a chat-like display does not give the model memory of past "
                "questions. Saved history lets you open an earlier run and see "
                "its result. Widgets rerun the page's Python code; session_state "
                "keeps the submitted query and response, so another POST requires "
                "submitting the form.",
            )
        ),
        simple_table(
            [tr("Действие", "Action"), tr("Что происходит", "What happens")],
            [
                [
                    tr("Задать вопрос", "Ask a question"),
                    tr(
                        "POST создаёт запуск; модель и инструменты работают на API-сервере.",
                        "POST creates a run; the model and tools execute on the API server.",
                    ),
                ],
                [
                    tr("Открыть историю", "Open history"),
                    tr(
                        "GET читает список и сохранённый запуск по UUID, без нового вызова модели.",
                        "GET reads the list and saved run by UUID without another model call.",
                    ),
                ],
                [
                    tr("Сохранить аналитику", "Save analytics"),
                    tr(
                        "В Dashboard: POST /api/reports заново считает и сохраняет снимок периода.",
                        "In Dashboard: POST /api/reports recomputes and saves a period snapshot.",
                    ),
                ],
                [
                    tr("Скачать JSON", "Download JSON"),
                    tr(
                        "Копия ответа API с точными десятичными строками и метаданными.",
                        "A copy of the API response with exact decimal strings and metadata.",
                    ),
                ],
            ],
            [145, W - 145],
            [CELL, CELL],
        ),
        p(tr("Как понимать ошибки", "How to interpret errors"), H2),
        p(
            tr(
                "Показатели Dashboard приходят отдельными GET-запросами, каждый "
                "со своим снимком базы. Сохранение отчёта запускает новый расчёт "
                "и показывает возвращённый снимок: при новых продажах он может "
                "отличаться от ранее открытого Dashboard.",
                "Dashboard metrics arrive in separate GET requests, each with "
                "its own database snapshot. Saving a report runs a new "
                "calculation and displays the returned snapshot: if new sales "
                "arrived, it may differ from the earlier Dashboard.",
            ),
            BODY_S,
        ),
        p(
            tr(
                "Нет соединения — проверь адрес API и процесс Uvicorn. 422 — "
                "исправь параметры или вопрос; 404 — сохранённого UUID нет; "
                "503 — проверь /ready, настройки и базу. Ошибка провайдера "
                "может дать 502, исчерпанный срок — 504. HTTP-тайм-аут UI "
                "не доказывает, что сервер остановил работу: прежде чем "
                "повторять POST, обнови историю запусков. Сохранённые ошибки "
                "доступны только в случаях, которые описаны на этапе 07.",
                "No connection: check the API address and Uvicorn process. "
                "422: correct the parameters or question; 404: the saved UUID "
                "does not exist; 503: check /ready, settings and the database. "
                "A provider failure may return 502 and a deadline failure 504. "
                "A UI HTTP timeout does not prove the server stopped working: "
                "refresh run history before retrying a POST. Stored errors "
                "are available only in the cases described in Stage 07.",
            ),
            BODY_S,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Что проверить самостоятельно.</b> Открой сентябрь, задай "
                "вопрос, скачай JSON, затем найди тот же UUID в истории. "
                "Сохрани обычный аналитический отчёт и открой его заново: "
                "чтение должно вернуть сохранённый снимок. После остановки API "
                "выполни новое действие и проверь понятное сообщение об ошибке. "
                f"Фактически выполненные проверки перечислены в разделе {number_of('Итоги проверки')}.",
                "<b>Try it yourself.</b> Open September, ask a question, download "
                "JSON and find the same UUID in history. Save an ordinary "
                "analytics report and reopen it: a read should return the saved "
                "snapshot. Stop the API, perform another action and check the "
                "clear error message. "
                f"The checks actually performed are listed in section {number_of('Итоги проверки')}.",
            ),
            VIOLET,
            VIOLET_L,
        ),
    ]
