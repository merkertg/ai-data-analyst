"""Bilingual sections 27-29: candidates, Isolation Forest and offline coverage."""

from reportlab.platypus import Spacer

from guide.diagrams import anomaly_flow
from guide.i18n import tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BODY_S,
    CELL,
    H2,
    SMALL,
    TEAL,
    VIOLET,
    VIOLET_L,
    Diagram,
    W,
    callout,
    code_block,
    p,
    simple_table,
)
from guide.toc import number_of, section

# Номер раздела с итогами: при вставке новых разделов он сдвигается сам.
RESULTS = number_of("Итоги проверки")


def add_stage05(story):
    """Explain detection defaults and the limits of positive-scenario coverage."""
    section(
        story,
        27,
        tr(
            "Необычное наблюдение — повод проверить данные и гипотезы.",
            "An unusual observation is a reason to inspect data and hypotheses.",
        ),
        TEAL,
    )
    story += [
        p(
            tr(
                "Этап 05 читает текущую базу и выдаёт <b>кандидатов</b>. Правила "
                "не знают сценарии A01–A05. Деньги считает SQL/Decimal; LLM "
                "не участвует. Параметры ниже — открытые учебные настройки.",
                "Stage 05 reads the current database and returns <b>candidates</b>. "
                "Rules do not know scenarios A01–A05. SQL/Decimal computes money; "
                "no LLM is involved. The settings below are explicit demo defaults.",
            )
        ),
        simple_table(
            [tr("Метод", "Method"), tr("Что и как проверяется", "What is checked")],
            [
                [
                    tr("Медиана и MAD", "Median and MAD"),
                    tr(
                        "Месячное количество и доля возвратов по категории; "
                        "доля скидки по региону и категории. Не менее 6 других "
                        "месяцев того же ряда; |z| ≥ 6.",
                        "Monthly quantity and refund ratio by category; discount "
                        "rate by region/category. At least 6 other months of the "
                        "same series; |z| ≥ 6.",
                    ),
                ],
                [
                    "MAD = 0",
                    tr(
                        "Разница строго больше max(25% от |медианы|, floor). "
                        "floor = 1 для количества, 0.01 для долей.",
                        "Difference strictly exceeds max(25% of |median|, floor). "
                        "floor = 1 for quantity, 0.01 for rates.",
                    ),
                ],
                [
                    "IQR",
                    tr(
                        "Количество оплаченной позиции выше Q3 + 3 × IQR "
                        "в своей категории; не менее 8 позиций.",
                        "Paid line quantity above Q3 + 3 × IQR within its "
                        "category; at least 8 lines.",
                    ),
                ],
                [
                    tr("Нулевой остаток", "Zero inventory"),
                    tr(
                        "Максимальный отрезок из ≥ 3 дней подряд с остатком 0. "
                        "Пропущенный день разрывает отрезок.",
                        "A maximal run of ≥ 3 consecutive zero-stock days. "
                        "A missing day breaks the run.",
                    ),
                ],
            ],
            [120, W - 120],
            [CELL, CELL],
        ),
        p(
            tr(
                "Месяц не задаёт себе ориентир", "A month does not set its own baseline"
            ),
            H2,
        ),
        p(
            tr(
                "Медиана — середина ряда; MAD — медиана абсолютных отклонений "
                "от неё. Проверяемый месяц исключён из ориентира (leave-one-out): "
                "z = 0.6745 × (x − median) / MAD. Пример: median = 100, MAD = 2, "
                "x = 60 → z = −13.49, кандидат по правилу |z| ≥ 6.",
                "The median is the middle value; MAD is the median absolute "
                "deviation from it. The scored month is excluded from its baseline "
                "(leave-one-out): z = 0.6745 × (x − median) / MAD. Example: "
                "median = 100, MAD = 2, x = 60 → z = −13.49, a candidate at |z| ≥ 6.",
            ),
            BODY_S,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Это ретроспектива.</b> Другие месяцы могут идти после "
                "проверяемого. Месячные детекторы берут только полные месяцы: "
                "обрезанные граничные месяцы пропускаются. Короткая история "
                "может не дать оценки. Прогноз не строится.",
                "<b>This is retrospective.</b> Other months may follow the month "
                "being scored. Monthly detectors use only complete months: "
                "clipped boundary months are skipped. Short histories may produce "
                "no score. This is not forecasting.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    section(
        story,
        28,
        tr(
            "Модель ищет сочетания признаков; финансовые суммы остаются точными.",
            "The model finds feature combinations; financial amounts remain exact.",
        ),
        VIOLET,
    )
    story += [
        p(
            tr(
                "<b>Isolation Forest</b> из scikit-learn дополняет простые "
                "правила. Одна строка — полный месяц, регион и категория. "
                "Нужно хотя бы 16 пригодных строк; полностью пустые группы "
                "не заменяются нулями.",
                "scikit-learn <b>Isolation Forest</b> complements simple rules. "
                "One row is a complete month, region and category. At least "
                "16 usable rows are required; entirely empty groups are "
                "not replaced with zeros.",
            )
        ),
        simple_table(
            [tr("Признак", "Feature"), tr("Смысл", "Meaning")],
            [
                [
                    tr("Количество / медиана", "Quantity / median"),
                    tr("Относительно своего ряда.", "Relative to its own series."),
                ],
                [
                    tr("Продажи / медиана", "Paid sales / median"),
                    tr("Отношение точных сумм.", "A ratio of exact amounts."),
                ],
                [
                    tr("Доля скидки", "Discount rate"),
                    tr("Взвешена по исходной стоимости.", "Weighted by gross value."),
                ],
                [
                    tr("Возвраты / продажи", "Refunds / sales"),
                    tr("Без продаж доля не определена.", "Undefined without sales."),
                ],
            ],
            [180, W - 180],
            [CELL, CELL],
        ),
        p(
            tr(
                "SQL независимо агрегирует продажи и возвраты. Денежные "
                "суммы остаются NUMERIC/Decimal. Только рассчитанные "
                "<b>безразмерные отношения</b> становятся float для модели.",
                "SQL aggregates sales and refunds independently. Monetary "
                "amounts remain NUMERIC/Decimal. Only the calculated "
                "<b>dimensionless ratios</b> become floats for the model.",
            ),
            BODY_S,
        ),
        p(tr("Воспроизводимый запуск", "Reproducible run"), H2),
        p(
            tr(
                "100 деревьев; random_state = 42; n_jobs = 1; "
                "contamination = auto. Кандидаты имеют decision_function &lt; 0. "
                "Оценка — не вероятность и не сумма потерь. Обучение и оценка "
                "используют предоставленный период, отдельной неизвестной "
                "выборки нет.",
                "100 trees; random_state = 42; n_jobs = 1; contamination = auto. "
                "Candidates have decision_function &lt; 0. The score is neither "
                "a probability nor a monetary loss. Fitting and scoring use "
                "the supplied period; there is no separate unseen holdout.",
            ),
            BODY_S,
        ),
        code_block(
            "uv run python -m app.analytics.anomalies \\\n"
            "  --start 2026-01-01 --end 2026-10-01 \\\n"
            "  --output /tmp/anomalies.json"
        ),
        p(
            tr(
                "Чтение — REPEATABLE READ READ ONLY, по DATABASE_URL. "
                "Без --output JSON печатается в терминал; существующий файл "
                "не перезаписывается. В отчёте: период, seed, счётчики "
                "наблюдений, настройки и findings с методом и доказательствами.",
                "Reads use REPEATABLE READ READ ONLY via DATABASE_URL. "
                "Without --output, JSON goes to the terminal; existing files "
                "are never overwritten. The report includes period, seed, "
                "observation counts, settings and findings with method and evidence.",
            ),
            SMALL,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Кандидат — не причина.</b> Нулевой остаток товара и "
                "меньшие продажи рядом по времени ещё не доказывают связь. "
                "Дополнительные кандидаты требуют проверки исходных строк.",
                "<b>A candidate is not a cause.</b> Zero inventory and lower "
                "sales close in time do not establish a causal link. Additional "
                "candidates require inspection of the underlying rows.",
            ),
            VIOLET,
            VIOLET_L,
        ),
    ]

    section(
        story,
        29,
        tr(
            "Эталон читает только отдельная offline-команда оценки.",
            "Only the separate offline evaluation command reads the answer key.",
        ),
        TEAL,
    )
    story += [
        Diagram(140, anomaly_flow),
        code_block(
            "uv run python -m app.analytics.evaluate \\\n"
            "  --report /tmp/anomalies.json \\\n"
            "  --ground-truth data/demo/ground_truth.json"
        ),
        p(
            tr(
                "Отчёт и эталон должны относиться к одному набору. Совпадения "
                "проверяются по периоду, типу сигнала и измерениям; для месячных "
                "сценариев также учитывается направление изменения. "
                "Полный локальный запуск 21.10.2026: <b>33 кандидата, 5/5 сценариев</b>.",
                "The report and answer key must describe the same dataset. "
                "Matching uses period, signal kind and dimensions; monthly "
                "scenarios also require the correct direction of change. "
                "Full local run on 21 Oct 2026: <b>33 candidates, 5/5 scenarios</b>.",
            ),
            BODY_S,
        ),
        simple_table(
            [tr("Сценарий", "Scenario"), tr("Проверяемое событие", "Event to check")],
            [
                [
                    "A01",
                    tr("Насосы: количество, сентябрь.", "Pumps: quantity, September."),
                ],
                [
                    "A02",
                    tr(
                        "Арматура, South: скидки, август.",
                        "Valves, South: discounts, August.",
                    ),
                ],
                [
                    "A03",
                    tr("Компрессоры: возвраты, июль.", "Compressors: refunds, July."),
                ],
                [
                    "A04",
                    tr(
                        "Один насос: ноль на складе, 10–19 сентября.",
                        "One pump: zero stock, 10–19 September.",
                    ),
                ],
                [
                    "A05",
                    tr(
                        "Датчики: позиция на 500 единиц, июнь.",
                        "Sensors: a 500-unit line, June.",
                    ),
                ],
            ],
            [75, W - 75],
            [CELL, CELL],
        ),
        p(
            tr(
                "7 кандидатов по месячной статистике + 1 IQR + 1 складской "
                "+ 24 Isolation Forest. Сценарии покрыты статистикой и правилами; "
                "это не оценка отдельно взятой модели. Два запуска с seed 42 "
                "дали одинаковый JSON.",
                "7 monthly-statistic candidates + 1 IQR + 1 stock rule + "
                "24 Isolation Forest. Statistics and rules covered the scenarios; "
                "this does not evaluate the model alone. Two seed 42 runs "
                "produced identical JSON.",
            ),
            SMALL,
        ),
        Spacer(1, 7),
        callout(
            tr(
                "<b>Покрытие ≠ precision.</b> Эталон содержит пять внедрённых "
                "положительных сценариев, но не размечает все обычные наблюдения. "
                "Даже 5/5 не означает точность 100% или качество на будущих данных. "
                "Дополнительный кандидат не становится автоматически ложным.",
                "<b>Coverage ≠ precision.</b> The answer key contains five injected "
                "positive scenarios, without labels for every ordinary observation. "
                "Even 5/5 does not mean 100% precision or quality on future data. "
                "An additional candidate is not automatically a false positive.",
            ),
            AMBER,
            AMBER_L,
        ),
        Spacer(1, 7),
        p(
            tr(
                "Проверки: положительные и обычные примеры, MAD = 0, "
                "короткая история, IQR, складские пропуски, повторяемость модели "
                "и точные SQL-признаки. Интеграционные тесты — только "
                f"TEST_DATABASE_URL с суффиксом _test. Результаты: раздел {RESULTS} "
                "и docs/VERIFICATION.md. Дальше — REST API, этап 06.",
                "Checks cover positive and ordinary cases, zero MAD, short "
                "history, IQR, inventory gaps, model reproducibility and exact "
                "SQL features. Integration tests use only TEST_DATABASE_URL "
                f"ending in _test. Results: section {RESULTS} and docs/VERIFICATION.md. "
                "Next is the REST API in Stage 06.",
            ),
            SMALL,
        ),
    ]
