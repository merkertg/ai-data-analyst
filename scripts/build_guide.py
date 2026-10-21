"""Наглядный PDF-гайд AI Data Analyst на русском и английском языках.

Запуск из корня проекта (ReportLab ставится только на время команды):

    uv run --locked --with 'reportlab==4.4.9' python scripts/build_guide.py

По умолчанию собираются обе версии: docs/guide/ai-data-analyst-guide.pdf
и docs/guide/ai-data-analyst-guide-en.pdf. --lang ru или --lang en
собирает одну. Тексты разделов лежат в scripts/guide/.
"""

import argparse
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from guide.diagrams import STAGES_DONE
from guide.i18n import LANGUAGES, loc, set_language, tr
from guide.layout import (
    HEX,
    INK,
    LINE,
    MARGIN,
    MUTED,
    PAGE_H,
    PAGE_W,
    WHITE,
    W,
    arrow,
    rbox,
    register_fonts,
    stat_tiles,
)
from guide.sources import app_facts, locked_dependencies, schema_counts
from guide.story import build_story
from guide.toc import (
    CONTENTS,
    STAGE_01_SECTIONS,
    STAGE_02_SECTIONS,
    STAGE_03_SECTIONS,
    STAGE_04_SECTIONS,
    STAGE_05_SECTIONS,
    STAGE_06_SECTIONS,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUIDE_DIR = PROJECT_ROOT / "docs/guide"
OUTPUTS = {
    "ru": GUIDE_DIR / "ai-data-analyst-guide.pdf",
    "en": GUIDE_DIR / "ai-data-analyst-guide-en.pdf",
}


# ---------- Колонтитулы ----------
def cover_page(c, doc):
    """Draw the cover, stage ranges and compact two-column contents."""
    verification = doc.verification
    c.saveState()
    c.setFillColor(INK)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # Декоративные круги приглушены и не спорят с текстом.
    c.setFillColor(HEX("#1E293B"))
    c.circle(PAGE_W - 40, PAGE_H - 60, 170, stroke=0, fill=1)
    c.setFillColor(HEX("#172554"))
    c.circle(PAGE_W - 120, PAGE_H - 250, 70, stroke=0, fill=1)
    left = MARGIN + 4
    c.setFillColor(HEX("#5EEAD4"))
    c.setFont("PT-Bold", 10)
    c.drawString(
        left,
        PAGE_H - 92,
        tr(
            "УЧЕБНЫЙ ПРОЕКТ № 2  ·  ВЫМЫШЛЕННАЯ КОМПАНИЯ INDUSTRIALFLOW",
            "LEARNING PROJECT NO. 2  ·  FICTIONAL COMPANY INDUSTRIALFLOW",
        ),
    )
    c.setFillColor(WHITE)
    c.setFont("PT-Bold", 44)
    c.drawString(left, PAGE_H - 150, "AI Data Analyst")
    c.setFillColor(HEX("#FDBA74"))
    c.setFont("PT-Bold", 17)
    c.drawString(
        left,
        PAGE_H - 180,
        tr(
            f"Этапы 01–{STAGES_DONE:02d} · API, база и аналитика",
            f"Stages 01–{STAGES_DONE:02d} · API, database and analytics",
        ),
    )
    c.setFont("PT", 14)
    c.setFillColor(HEX("#CBD5E1"))
    y = PAGE_H - 208
    for line in simpleSplit(
        tr(
            "Наглядное руководство: окружение uv, API на FastAPI, PostgreSQL в Docker, "
            "миграции Alembic, SQL, воспроизводимые данные, аналитика, аномалии, "
            "REST API, тесты и CI.",
            "A visual guide: the uv environment, a FastAPI API, PostgreSQL in Docker, "
            "Alembic migrations, SQL, reproducible data, analytics, anomalies, "
            "a REST API, tests and CI.",
        ),
        "PT",
        14,
        W - 30,
    ):
        c.drawString(left, y, line)
        y -= 19

    # Мини-схема: путь запроса до базы.
    steps = [
        (tr("Клиент", "Client"), tr("curl или /docs", "curl or /docs")),
        ("Uvicorn", tr("сервер :8000", "server :8000")),
        ("FastAPI", "/api · /ready"),
        ("SQLAlchemy", tr("пул и сессии", "pool and sessions")),
        ("PostgreSQL", tr("данные и отчёты", "data and reports")),
    ]
    top = PAGE_H - 370
    box_w, box_h, gap = 86, 54, 13
    total = len(steps) * box_w + (len(steps) - 1) * gap
    x0 = (PAGE_W - total) / 2
    accents = ["#FDBA74", "#5EEAD4", "#60A5FA", "#A78BFA", "#86EFAC"]
    for index, (title, sub) in enumerate(steps):
        x = x0 + index * (box_w + gap)
        rbox(c, x, top, box_w, box_h, HEX("#1E293B"), HEX(accents[index]), r=9, lw=1.4)
        c.setFillColor(WHITE)
        c.setFont("PT-Bold", 11)
        c.drawCentredString(x + box_w / 2, top + 31, title)
        c.setFillColor(HEX("#94A3B8"))
        c.setFont("PT", 8.6)
        c.drawCentredString(x + box_w / 2, top + 16, sub)
        if index < len(steps) - 1:
            arrow(
                c,
                x + box_w + 2,
                top + box_h / 2,
                x + box_w + gap - 2,
                top + box_h / 2,
                HEX("#94A3B8"),
                1.2,
                4.5,
            )
    c.setFillColor(HEX("#94A3B8"))
    c.setFont("PT-Italic", 9.5)
    c.drawCentredString(
        PAGE_W / 2,
        top - 22,
        tr(
            "Числа в отчётах считает код, а данные защищает сама база.",
            "Code computes the numbers; the database itself guards the data.",
        ),
    )

    tests = verification["tests"]
    checks = verification["checks"]
    passed_checks = sum(1 for item in checks if item["status"] == "pass")
    stat_tiles(
        c,
        MARGIN,
        352,
        W,
        74,
        [
            (f"{STAGES_DONE} / 10", tr("этапов курса завершены", "course stages done")),
            (
                f"{tests['passed']} / {tests['total']}",
                tr("автотестов прошли", "tests passed"),
            ),
            (
                f"{passed_checks} / {len(checks)}",
                tr("локальных проверок PASS", "local checks PASS"),
            ),
            (str(doc.counts["tables"]), tr("таблиц с данными", "data tables")),
            (str(doc.lock_packages), tr("пакетов в uv.lock", "packages in uv.lock")),
        ],
        HEX("#1E293B"),
        WHITE,
        HEX("#94A3B8"),
        HEX("#334155"),
    )
    c.setFillColor(HEX("#CBD5E1"))
    c.setFont("PT-Bold", 10)
    c.drawString(MARGIN, 318, tr("Что внутри", "Contents"))
    c.setFont("PT", 7.8)
    c.setFillColor(HEX("#64748B"))
    c.drawString(
        MARGIN + 80,
        318,
        tr(
            f"01: {STAGE_01_SECTIONS[0]}–{STAGE_01_SECTIONS[-1]} · "
            f"02: {STAGE_02_SECTIONS[0]}–{STAGE_02_SECTIONS[-1]} · "
            f"03: {STAGE_03_SECTIONS[0]}–{STAGE_03_SECTIONS[-1]} · "
            f"04: {STAGE_04_SECTIONS[0]}–{STAGE_04_SECTIONS[-1]} · "
            f"05: {STAGE_05_SECTIONS[0]}–{STAGE_05_SECTIONS[-1]} · "
            f"06: {STAGE_06_SECTIONS[0]}–{STAGE_06_SECTIONS[-1]}",
            f"01: {STAGE_01_SECTIONS[0]}–{STAGE_01_SECTIONS[-1]} · "
            f"02: {STAGE_02_SECTIONS[0]}–{STAGE_02_SECTIONS[-1]} · "
            f"03: {STAGE_03_SECTIONS[0]}–{STAGE_03_SECTIONS[-1]} · "
            f"04: {STAGE_04_SECTIONS[0]}–{STAGE_04_SECTIONS[-1]} · "
            f"05: {STAGE_05_SECTIONS[0]}–{STAGE_05_SECTIONS[-1]} · "
            f"06: {STAGE_06_SECTIONS[0]}–{STAGE_06_SECTIONS[-1]}",
        ),
    )
    c.setFont("PT", 9.3)
    rows = (len(CONTENTS) + 1) // 2
    for index, (ru, en) in enumerate(CONTENTS):
        column, row = divmod(index, rows)
        number = index + 1
        if number in STAGE_01_SECTIONS:
            c.setFillColor(HEX("#93C5FD"))
        elif number in STAGE_02_SECTIONS:
            c.setFillColor(HEX("#5EEAD4"))
        elif number in STAGE_03_SECTIONS:
            c.setFillColor(HEX("#C4B5FD"))
        elif number in STAGE_04_SECTIONS:
            c.setFillColor(HEX("#FDBA74"))
        elif number in STAGE_05_SECTIONS:
            c.setFillColor(HEX("#86EFAC"))
        elif number in STAGE_06_SECTIONS:
            c.setFillColor(HEX("#FDE68A"))
        else:
            c.setFillColor(HEX("#94A3B8"))
        # 19 строк в колонке: шаг 11.5 оставляет последнюю строку выше линии y=82.
        c.drawString(MARGIN + column * 250, 300 - row * 11.5, f"{number}  {tr(ru, en)}")
    c.setStrokeColor(HEX("#334155"))
    c.line(MARGIN, 82, PAGE_W - MARGIN, 82)
    c.setFillColor(HEX("#64748B"))
    c.setFont("PT", 8.4)
    environment = verification["environment"]
    c.drawString(
        MARGIN,
        66,
        tr("Проверка", "Verified")
        + f" {verification['checked_at']} · "
        + tr("коммит", "commit")
        + f" {verification['base_commit']} · uv {environment['uv']} · "
        f"Python {environment['python']} · PostgreSQL {environment['postgres']} · "
        f"{loc(environment['os'])}",
    )
    c.drawString(
        MARGIN,
        53,
        tr(
            "Этапы: docs/STAGE_01.md–STAGE_06.md; отчёт: docs/VERIFICATION.md",
            "Stage guides: docs/STAGE_01.md–STAGE_06.md; "
            "instructions: docs/instructions/",
        ),
    )
    c.restoreState()


def content_page(c, doc):
    """Нижний колонтитул обычной страницы."""
    c.saveState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, 13 * mm, PAGE_W - MARGIN, 13 * mm)
    c.setFillColor(MUTED)
    c.setFont("PT", 8)
    c.drawString(
        MARGIN,
        9 * mm,
        tr(
            f"AI Data Analyst · этапы 01–{STAGES_DONE:02d} · наглядное руководство",
            f"AI Data Analyst · stages 01–{STAGES_DONE:02d} · visual guide",
        ),
    )
    c.drawRightString(PAGE_W - MARGIN, 9 * mm, str(doc.page))
    c.restoreState()


# ---------- Проверка данных ----------
def _is_text(value) -> bool:
    """Общая строка или пара {"ru": ..., "en": ...} с непустыми строками."""
    if isinstance(value, str):
        return bool(value)
    return isinstance(value, dict) and all(
        isinstance(value.get(lang), str) and value[lang] for lang in LANGUAGES
    )


def load_verification(path):
    """Прочитать сводку проверки и отклонить отсутствующие или неверные данные."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in (
        "checked_at",
        "base_commit",
        "environment",
        "tests",
        "checks",
        "http",
        "remote_ci",
        "remaining",
    ):
        if key not in data:
            raise ValueError(f"В verification.json отсутствует {key}")
    tests = data["tests"]
    for key in ("total", "unit", "integration", "passed", "failed", "skipped"):
        if type(tests.get(key)) is not int or tests[key] < 0:
            raise ValueError(f"tests.{key}: требуется неотрицательное целое число")
    if tests["unit"] + tests["integration"] != tests["total"]:
        raise ValueError("unit + integration не равно total")
    if tests["passed"] + tests["failed"] + tests["skipped"] != tests["total"]:
        raise ValueError("passed + failed + skipped не равно total")
    environment = data["environment"]
    if not _is_text(environment.get("os")) or not all(
        isinstance(environment.get(key), str)
        for key in ("uv", "python", "docker", "postgres")
    ):
        raise ValueError("environment: нужны os, uv, python, docker, postgres")
    for item in data["checks"]:
        if (
            not _is_text(item.get("name"))
            or not _is_text(item.get("result"))
            or not isinstance(item.get("command"), str)
            or item.get("status") not in {"pass", "fail"}
        ):
            raise ValueError("Для каждой проверки нужны name, command, result, status")
    for item in data["http"]:
        if not isinstance(item.get("status"), str) or not _is_text(item.get("request")):
            raise ValueError("Для каждого HTTP-ответа нужны request и status")
        if not _is_text(item.get("body")):
            raise ValueError("Для каждого HTTP-ответа нужно body")
    remote = data["remote_ci"]
    if remote.get("status") not in {"not_verified", "passed", "failed"} or not _is_text(
        remote.get("detail")
    ):
        raise ValueError("remote_ci: нужны допустимый status и пояснение detail")
    if not isinstance(data["remaining"], list) or not all(
        _is_text(item) for item in data["remaining"]
    ):
        raise ValueError("remaining: требуется список текстов")
    return data


# ---------- Сборка ----------
def build_guide(output, verification, lang):
    """Собрать одну языковую версию; старый PDF заменяется только при успехе."""
    set_language(lang)
    dependencies, lock_packages = locked_dependencies()
    facts = app_facts()
    counts = schema_counts()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = Path(tempfile.gettempdir()) / f"{output.stem}-before-{stamp}.pdf"
        shutil.copy2(output, backup)
        print(f"Исходный PDF сохранён: {backup}")
    with tempfile.NamedTemporaryFile(
        prefix=".ai-data-analyst-guide-",
        suffix=".pdf",
        dir=output.parent,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        document = BaseDocTemplate(
            str(temporary_path),
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=16 * mm,
            bottomMargin=17 * mm,
            title="AI Data Analyst - "
            + tr(
                f"этапы 01–{STAGES_DONE:02d}: API, база и аналитика",
                f"stages 01–{STAGES_DONE:02d}: API, database and analytics",
            ),
            author="AI Data Analyst",
            subject=tr(
                "uv, FastAPI, PostgreSQL, SQL, данные, аналитика, тесты и CI",
                "uv, FastAPI, PostgreSQL, SQL, data, analytics, tests and CI",
            ),
            lang=lang,
        )
        # Обложка читает эти значения во время отрисовки.
        document.verification = verification
        document.lock_packages = lock_packages
        document.counts = counts
        frame = Frame(
            MARGIN,
            17 * mm,
            W,
            PAGE_H - 33 * mm,
            id="body",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover")
        document.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[cover_frame], onPage=cover_page),
                PageTemplate(id="content", frames=[frame], onPage=content_page),
            ]
        )
        document.build(
            build_story(verification, dependencies, lock_packages, facts, counts)
        )
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Руководство создано ({lang}): {output}")


def main(argv=None):
    """Разобрать аргументы и собрать PDF только при явном запуске скрипта."""
    parser = argparse.ArgumentParser(
        description="Собрать PDF-гайд AI Data Analyst на русском и английском."
    )
    parser.add_argument(
        "--lang",
        choices=[*LANGUAGES, "all"],
        default="all",
        help="язык сборки; по умолчанию обе версии",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="путь к PDF; только вместе с --lang ru или --lang en",
    )
    parser.add_argument(
        "--verification",
        type=Path,
        default=GUIDE_DIR / "verification.json",
    )
    args = parser.parse_args(argv)
    if args.output and args.lang == "all":
        parser.error("--output требует --lang ru или --lang en")
    verification = load_verification(args.verification.resolve())
    register_fonts()
    languages = LANGUAGES if args.lang == "all" else (args.lang,)
    for lang in languages:
        output = args.output.resolve() if args.output else OUTPUTS[lang]
        build_guide(output, verification, lang)


if __name__ == "__main__":
    main()
