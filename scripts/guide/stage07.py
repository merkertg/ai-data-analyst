"""Bilingual sections 33–36: agent tools, the loop, evidence, providers and history."""

from reportlab.platypus import Spacer

from guide.diagrams import agent_loop
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
    SMALL,
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

# Номер раздела с итогами: при вставке новых разделов он сдвигается сам.
RESULTS = number_of("Итоги проверки")


def add_stage07(story):
    """Explain agent tools, evidence checks and their practical limits."""
    section(
        story,
        number_of("Инструменты агента"),
        tr(
            "Модель выбирает функцию из списка, а не пишет SQL.",
            "The model picks a function from a list; it never writes SQL.",
        ),
        TEAL,
    )
    story += [
        p(
            tr(
                "Этап 07 отвечает на вопросы обычным языком: «Почему в сентябре "
                "снизилась выручка?». Языковая модель понимает вопрос, выбирает "
                "инструменты и формулирует вывод. Числа по-прежнему считает "
                "код: инструменты используют функции REST API и точные SQL-запросы.",
                "Stage 07 answers plain-language questions such as “Why did "
                "revenue fall in September?”. The language model understands the "
                "question, picks tools and phrases the conclusion. Code still "
                "computes every number: the tools use REST API functions and "
                "exact SQL queries.",
            )
        ),
        simple_table(
            [tr("Инструмент", "Tool"), tr("Что возвращает", "Returns")],
            [
                [
                    mono("get_data_coverage"),
                    tr(
                        "Даты продаж, возвратов, остатков; названия категорий и регионов.",
                        "Dates of sales, refunds and stock; category and region names.",
                    ),
                ],
                [
                    mono("get_revenue"),
                    tr("Итоги периода и месяцы.", "Period totals and months."),
                ],
                [
                    mono("compare_periods"),
                    tr(
                        "Все показатели двух периодов и изменения.",
                        "All metrics of two periods and changes.",
                    ),
                ],
                [
                    mono("get_sales_by_category"),
                    tr(
                        "Изменение выручки по категориям и доли.",
                        "Revenue change by category and shares.",
                    ),
                ],
                [
                    mono("get_sales_by_region"),
                    tr("То же по регионам.", "The same by region."),
                ],
                [
                    mono("get_top_products"),
                    tr("Товары с наибольшими продажами.", "Top-selling products."),
                ],
                [
                    mono("get_refund_statistics"),
                    tr(
                        "Возвраты по категориям и их доля к продажам.",
                        "Refunds per category and their rate to sales.",
                    ),
                ],
                [
                    mono("detect_anomalies"),
                    tr(
                        "Кандидаты этапа 05: правила, затем Isolation Forest.",
                        "Stage 05 candidates: rules, then Isolation Forest.",
                    ),
                ],
                [
                    mono("get_inventory_history"),
                    tr(
                        "Дни с нулевым остатком по товарам.",
                        "Zero-stock days per product.",
                    ),
                ],
            ],
            [175, W - 175],
            [CELL, CELL],
        ),
        p(tr("Строгие аргументы", "Strict arguments"), H2),
        code_block(
            "class ListArguments(PeriodArguments):\n"
            "    category: str | None = Field(max_length=100)\n"
            "    limit: int = Field(ge=1, le=20)\n"
            '# model_config: extra="forbid", strict=True'
        ),
        Spacer(1, 6),
        p(
            tr(
                "Из модели строится JSON Schema с <b>strict: true</b>: модель обязана "
                "прислать аргументы точно по схеме. Сервер всё равно проверяет их "
                "заново — до первого SQL. Лишнее поле, число строкой, повтор ключа, "
                "обратный период или больше 24 месяцев — модель получает ошибку "
                "и может исправить вызов. Такие случаи проверены тестом, "
                "который запрещает даже открыть сессию базы.",
                "The model becomes a JSON Schema with <b>strict: true</b>: the model "
                "must send arguments exactly by the schema. The server validates "
                "them again anyway, before any SQL. An extra field, a number as "
                "text, a repeated key, a reversed period or more than 24 months "
                "returns an error the model can correct. A test covers such cases "
                "and forbids even opening a database session.",
            ),
            BODY_S,
        ),
        Spacer(1, 4),
        code_block(
            '{"ok": false, "error": {"code": "invalid_arguments",\n'
            ' "message": "period: start must be earlier than the exclusive end"}}'
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Почему не произвольный SQL.</b> Тяжёлые запросы, лишние таблицы "
                "и двойной счёт этапа 04. Имя инструмента выбирает элемент словаря, "
                "аргументы — данные, запрос заранее написан и выполняется в сессии "
                "REPEATABLE READ READ ONLY. Результат больше 16 000 символов "
                "заменяется ошибкой: он не поместился бы в контекст.",
                "<b>Why no free-form SQL.</b> Heavy queries, extra tables and the "
                "double counting of Stage 04. The tool name selects a dictionary "
                "entry, arguments are data, and the query is pre-written and runs "
                "in a REPEATABLE READ READ ONLY session. A result over 16,000 "
                "characters becomes an error: it would not fit the context.",
            ),
            TEAL,
            GREEN_L,
        ),
    ]

    section(
        story,
        number_of("Цикл tool calling"),
        tr(
            "Сервер управляет циклом; модель только предлагает следующий шаг.",
            "The server owns the loop; the model only proposes the next step.",
        ),
        BLUE,
    )
    story += [
        Diagram(132, agent_loop),
        Spacer(1, 6),
        p(
            tr(
                "На каждом шаге runtime отправляет модели всю историю: вопрос, "
                "прошлые вызовы и их результаты. Модель отвечает либо вызовами "
                "инструментов — сразу несколькими, — либо отчётом. Результат "
                "каждого вызова возвращается с его <b>call_id</b>. Второй шаг "
                "зависит от первого: сначала сравнение, категории, регионы и "
                "возвраты, затем аномалии и остатки главной категории.",
                "On every step the runtime sends the whole history: the question, "
                "earlier calls and their results. The model answers with tool "
                "calls, several at once, or with a report. Each result goes back "
                "with its <b>call_id</b>. The second step depends on the first: "
                "comparison, categories, regions and refunds first, then anomalies "
                "and stock of the main category.",
            ),
            BODY_S,
        ),
        Spacer(1, 4),
        simple_table(
            [
                tr("Лимит", "Limit"),
                tr("По умолчанию", "Default"),
                tr("Что ограничивает", "What it bounds"),
            ],
            [
                [mono("AGENT_MAX_STEPS"), "8", tr("Ответы модели", "Model answers")],
                [
                    mono("AGENT_MAX_TOOL_CALLS"),
                    "16",
                    tr(
                        "Вызовы; пакет сверх лимита отклоняется целиком",
                        "Calls; an over-limit batch is rejected whole",
                    ),
                ],
                [
                    mono("AGENT_MAX_CORRECTIONS"),
                    "2",
                    tr(
                        "Повторы отчёта после проверки",
                        "Report retries after the check",
                    ),
                ],
                [
                    mono("AGENT_TIMEOUT_SECONDS"),
                    "120",
                    tr(
                        "Общий срок, проверяемый между операциями",
                        "Overall deadline checked between operations",
                    ),
                ],
                [
                    tr("контекст", "context"),
                    tr("120 000 симв.", "120,000 chars"),
                    tr("Вся история; больше — 413", "Whole history; more is 413"),
                ],
            ],
            [175, 90, W - 265],
            [CELL, CELL, CELL],
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>store=False.</b> Ответ не сохраняется для продолжения "
                "диалога; история отправляется целиком, вместе с "
                "зашифрованными рассуждениями модели. "
                "Лимиты задаёт сервер: число шагов и вызовов конечно. Общий срок "
                "проверяется между операциями; уже запущенный синхронный SQL "
                "принудительно не прерывается. Тесты проверяют лимиты "
                "со сценарным провайдером — без сети и случайности.",
                "<b>store=False.</b> The response is not saved for a later "
                "conversation turn; the whole history is sent again, including "
                "the model's encrypted reasoning. The server "
                "sets finite step and call limits. The overall deadline is checked "
                "between operations; active synchronous SQL is not forcibly "
                "interrupted. Tests check limits with a scripted "
                "provider, without a network or randomness.",
            ),
            BLUE,
            VIOLET_L,
        ),
    ]

    section(
        story,
        number_of("Отчёт и доказательства"),
        tr(
            "Распознанные числовые записи сверяются с доказательствами.",
            "Recognised numeric literals are matched to evidence.",
        ),
        AMBER,
    )
    story += [
        simple_table(
            [
                tr("Поле AnalysisReport", "AnalysisReport field"),
                tr("Содержание", "Content"),
            ],
            [
                [
                    mono("language"),
                    tr(
                        "ru или en — язык вопроса.",
                        "ru or en: the question's language.",
                    ),
                ],
                [
                    mono("summary"),
                    tr(
                        "Короткий ответ на языке вопроса.",
                        "Short answer in the question's language.",
                    ),
                ],
                [
                    mono("facts"),
                    tr(
                        "Утверждения со ссылками evidence.",
                        "Statements with evidence references.",
                    ),
                ],
                [
                    mono("hypotheses"),
                    tr(
                        "Возможные объяснения, не доказанные причины.",
                        "Possible explanations, not proven causes.",
                    ),
                ],
                [
                    mono("recommendations"),
                    tr(
                        "Что проверить или сделать дальше.", "What to check or do next."
                    ),
                ],
                [
                    mono("limitations"),
                    tr(
                        "Чего анализ не покрывает.", "What the analysis does not cover."
                    ),
                ],
            ],
            [140, W - 140],
            [CELL, CELL],
        ),
        Spacer(1, 6),
        code_block(
            '{"call_id": "mock-category", "field": "contributions.0.delta",\n'
            ' "value": "-138597069.79"}'
        ),
        Spacer(1, 6),
        p(
            tr(
                "Перед приёмом отчёта <b>check_report</b> проверяет два правила. "
                "1) Доказательство настоящее: вызов был в этом запуске, завершился "
                "успешно, путь ведёт к одному значению, и оно совпадает символ в "
                "символ; у факта есть хотя бы одно доказательство. "
                "2) Распознанные числа сверены: в фактах и гипотезах — "
                "их собственными доказательствами, в summary, рекомендациях "
                "и limitations — "
                "любым проверенным. Знак можно опустить, разряды — разделить. "
                "Исключены ISO-даты, годы в календарном контексте, коды вроде "
                "A01 и цифры в процитированных названиях. Сумма 2000 RUB "
                "остаётся числом, которому нужно доказательство.",
                "Before a report is accepted, <b>check_report</b> applies two rules. "
                "1) Evidence is real: the call happened in this run, succeeded, the "
                "path leads to one value, and it matches exactly; every fact "
                "has at least one evidence item. 2) Recognised numbers match: "
                "in facts and hypotheses by their own evidence, in the summary, "
                "recommendations and limitations by any verified "
                "evidence. The sign may be dropped and digits grouped. ISO dates, "
                "calendar-context years, codes such as A01 and digits in cited "
                "names are excluded. An amount of 2000 RUB still needs evidence.",
            ),
            BODY_S,
        ),
        Spacer(1, 4),
        simple_table(
            [tr("Текст отчёта", "Report text"), tr("Проверка", "Check")],
            [
                [
                    tr(
                        "«упала на 291 500.00 (−94.34%)», оба в evidence",
                        "“fell by 291,500.00 (−94.34%)”, both in evidence",
                    ),
                    tr("принят", "accepted"),
                ],
                [
                    tr(
                        "«упала на 300000.00», evidence −291500.00",
                        "“fell by 300000.00”, evidence −291500.00",
                    ),
                    mono("number '300000.00' is not in its evidence"),
                ],
                [
                    tr(
                        "evidence −291000.00, в результате −291500.00",
                        "evidence −291000.00, result −291500.00",
                    ),
                    mono("is '-291500.00', not '-291000.00'"),
                ],
                [
                    tr("summary: «то есть 95%»", "summary: “that is 95%”"),
                    mono("number '95' is not in any evidence"),
                ],
            ],
            [230, W - 230],
            [CELL, CELL],
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Не сошлось — исправление.</b> Модель получает список проблем и "
                "присылает отчёт снова, не больше двух раз; потом — ошибка 502. "
                "Проверка не доказывает метрику, знак или причинную связь; "
                "числа словами и другие обозначения могут не распознаваться. "
                "Причины записываются как гипотезы. Найдено при разработке: "
                "«Demo pumps 01» — цифры названия, а не число; названия из "
                "доказательств вырезаются перед поиском чисел.",
                "<b>Mismatch means a correction.</b> The model gets the list of "
                "problems and sends the report again, at most twice; then a 502. "
                "The check does not prove metric identity, sign or causation; "
                "number words and other notations may not be recognised. "
                "Causes are written as hypotheses. Found during development: "
                "“Demo pumps 01” holds name digits, not a figure; names from the "
                "evidence are removed before numbers are searched.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    section(
        story,
        number_of("Провайдеры и история"),
        tr(
            "Mock — для показа без ключа, OpenAI — по явной настройке.",
            "Mock for a keyless demo, OpenAI only when configured.",
        ),
        VIOLET,
    )
    story += [
        simple_table(
            [tr("Провайдер", "Provider"), tr("Как работает", "How it works")],
            [
                [
                    "mock",
                    tr(
                        "По умолчанию. Четыре шага по настоящим инструментам; из "
                        "вопроса берёт месяц, год и язык. Отчёт проходит ту же "
                        "проверку и помечен как демонстрационный.",
                        "Default. Four steps over the real tools; reads the month, "
                        "year and language of the question. The report passes the "
                        "same check and is marked as a demo.",
                    ),
                ],
                [
                    "openai",
                    tr(
                        "Responses API: strict-инструменты, parallel_tool_calls, "
                        "strict json_schema отчёта, store=False, фиксированный адрес, "
                        "без повторов и без модели по умолчанию.",
                        "Responses API: strict tools, parallel_tool_calls, a strict "
                        "json_schema report, store=False, a fixed URL, no retries "
                        "and no default model.",
                    ),
                ],
            ],
            [80, W - 80],
            [CELL, CELL],
        ),
        Spacer(1, 6),
        code_block(
            "curl -X POST http://127.0.0.1:8000/api/agent/runs \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            '  -d \'{"question": "Почему в сентябре снизилась выручка?"}\''
        ),
        p(tr("История расследований", "Investigation history"), H2),
        p(
            tr(
                "Успех и обработанные ошибки LLM сохраняются в <b>agent_runs</b> "
                "(миграция 0003), если запись в базу успешна: вопрос, провайдер, "
                "модель, отчёт или ошибка, обработанные вызовы, токены и время. "
                "Ошибка 502/503/504/413 тогда содержит run_id. Ошибки настроек "
                "до старта и недоступная база — без сохранённого запуска. "
                "GET /api/agent/runs — список, GET /api/agent/runs/{id} — "
                "полный сохранённый запуск. JSONB(none_as_null=True) "
                "пишет None как SQL NULL; CHECK проверен тестом.",
                "Successes and caught LLM failures are saved in <b>agent_runs</b> "
                "(migration 0003) when storage succeeds: question, provider, "
                "model, report or error, processed calls, tokens and time. "
                "A 502/503/504/413 then includes a run_id. Pre-run settings "
                "failures and an unavailable database have no stored run. "
                "GET /api/agent/runs lists runs; GET /api/agent/runs/{id} "
                "returns the full saved run. JSONB(none_as_null=True) "
                "writes None as SQL NULL; the CHECK is tested.",
            ),
            BODY_S,
        ),
        p(tr("Полный набор, mock-провайдер", "Full dataset, mock provider"), H2),
        simple_table(
            [
                tr("Вопрос", "Question"),
                tr("Главное в отчёте", "Report highlights"),
                tr("Время", "Time"),
            ],
            [
                [
                    tr(
                        "Почему в сентябре снизилась выручка?",
                        "Why did revenue fall in September?",
                    ),
                    tr(
                        "−165 497 371.86 (−26.18%); насосы 83.75%; Demo pumps 01 — 10 дней без остатка",
                        "−165,497,371.86 (−26.18%); pumps 83.75%; Demo pumps 01 — 10 zero-stock days",
                    ),
                    tr("311 мс", "311 ms"),
                ],
                [
                    "Why did revenue fall in July 2026?",
                    tr(
                        "−80 258 104.27 (−13.60%); компрессоры 99.81%; возвраты 30.28%",
                        "−80,258,104.27 (−13.60%); compressors 99.81%; refunds 30.28%",
                    ),
                    tr("251 мс", "251 ms"),
                ],
            ],
            [150, W - 215, 65],
            [CELL, CELL, CELL],
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Настоящая модель OpenAI не проверялась</b> — ключа нет. "
                "Проверены формат запроса, разбор ответов и ошибки SDK на поддельном "
                "SDK. Маршрут остаётся def: SDK и база синхронные, FastAPI держит "
                "запуск в пуле потоков. Авторизации нет — только 127.0.0.1.",
                "<b>A real OpenAI model was not tested</b>: there is no key. The "
                "request format, response parsing and SDK errors were tested with "
                "a fake SDK. The route stays def: the SDK and the database are "
                "synchronous, FastAPI runs the request in its thread pool. No "
                "authentication yet: 127.0.0.1 only.",
            ),
            AMBER,
            AMBER_L,
        ),
        Spacer(1, 6),
        callout(
            tr(
                "В mock-примерах видны признаки A01, A03 и A04; эталон не читался. Это не оценка точности агента. "
                f"Результаты: раздел {RESULTS} и docs/VERIFICATION.md. "
                "Дальше — интерфейс Streamlit, этап 08.",
                "Mock examples show signs of A01, A03 and A04 without reading "
                f"ground_truth.json; this is not an accuracy evaluation. Results: section {RESULTS} and "
                "docs/VERIFICATION.md. Next is the Streamlit UI in Stage 08.",
            ),
            GREEN,
            GREEN_L,
            SMALL,
        ),
    ]
