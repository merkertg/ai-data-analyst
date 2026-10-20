"""Наглядный PDF-гайд AI Data Analyst: этап 01 и результаты его проверки.

Запуск из корня проекта (ReportLab ставится только на время команды):

    uv run --locked --with 'reportlab==4.4.9' python scripts/build_guide.py
"""

import argparse
import ast
import json
import re
import shutil
import sys
import tempfile
import tomllib
from datetime import datetime
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Стрелок нет в PT Sans: такие символы рисуются шрифтом PT Mono.
ARROWS = "→←↓"


def register_fonts():
    """Зарегистрировать кириллицу PT на Mac или DejaVu Sans на Linux."""
    mac_sans = Path("/System/Library/Fonts/Supplemental/PTSans.ttc")
    mac_mono = Path("/System/Library/Fonts/Supplemental/PTMono.ttc")
    if mac_sans.is_file() and mac_mono.is_file():
        font_files = {
            "PT": (mac_sans, 0),
            "PT-Bold": (mac_sans, 7),
            "PT-Italic": (mac_sans, 1),
            "PT-BoldItalic": (mac_sans, 6),
            "Mono": (mac_mono, 1),
            "Mono-Bold": (mac_mono, 0),
        }
    else:
        root = Path("/usr/share/fonts/truetype/dejavu")
        font_files = {
            "PT": (root / "DejaVuSans.ttf", 0),
            "PT-Bold": (root / "DejaVuSans-Bold.ttf", 0),
            "PT-Italic": (root / "DejaVuSans-Oblique.ttf", 0),
            "PT-BoldItalic": (root / "DejaVuSans-BoldOblique.ttf", 0),
            "Mono": (root / "DejaVuSansMono.ttf", 0),
            "Mono-Bold": (root / "DejaVuSansMono-Bold.ttf", 0),
        }
    missing = [str(path) for path, _ in font_files.values() if not path.is_file()]
    if missing:
        raise RuntimeError("Не найдены шрифты с кириллицей: " + ", ".join(missing))
    for name, (path, index) in font_files.items():
        pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=index))
    pdfmetrics.registerFontFamily(
        "PT",
        normal="PT",
        bold="PT-Bold",
        italic="PT-Italic",
        boldItalic="PT-BoldItalic",
    )
    pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold")


# ---------- Цвета ----------
HEX = colors.HexColor
INK = HEX("#0F172A")
TEXT = HEX("#1E293B")
MUTED = HEX("#64748B")
LINE = HEX("#CBD5E1")
SOFT = HEX("#F1F5F9")
WHITE = colors.white
BLUE, BLUE_L = HEX("#2563EB"), HEX("#DBEAFE")
TEAL, TEAL_L = HEX("#0F766E"), HEX("#CCFBF1")
ORANGE, ORANGE_L = HEX("#C2410C"), HEX("#FFEDD5")
VIOLET, VIOLET_L = HEX("#6D28D9"), HEX("#EDE9FE")
GREEN, GREEN_L = HEX("#15803D"), HEX("#DCFCE7")
AMBER, AMBER_L = HEX("#B45309"), HEX("#FEF3C7")
SLATE_L = HEX("#E2E8F0")

PAGE_W, PAGE_H = A4
MARGIN = 17 * mm
W = PAGE_W - 2 * MARGIN

# ---------- Стили текста ----------
BODY = ParagraphStyle("body", fontName="PT", fontSize=10.5, leading=15, textColor=TEXT)
BODY_S = ParagraphStyle("bodys", parent=BODY, fontSize=9.5, leading=13.5)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.6, leading=12, textColor=MUTED)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9, leading=12.2)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName="PT-Bold")
CELL_M = ParagraphStyle(
    "cellm", parent=CELL, fontName="Mono", fontSize=8.3, leading=11.5
)
HEAD = ParagraphStyle("head", parent=CELL, fontName="PT-Bold", textColor=WHITE)
H2 = ParagraphStyle(
    "h2",
    parent=BODY,
    fontName="PT-Bold",
    fontSize=13,
    leading=17,
    textColor=INK,
    spaceBefore=6,
    spaceAfter=5,
)
CODE = ParagraphStyle(
    "code", fontName="Mono", fontSize=8.4, leading=11.4, textColor=INK
)
QUESTION = ParagraphStyle(
    "question", parent=BODY, fontName="PT-Bold", fontSize=10, leading=14
)


def p(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    """Абзац с разметкой ReportLab; стрелки подставляются шрифтом PT Mono."""
    for arrow_char in ARROWS:
        text = text.replace(arrow_char, f'<font name="Mono">{arrow_char}</font>')
    return Paragraph(text, style)


def mono(text: str) -> str:
    """Встроенный моноширинный фрагмент; угловые скобки экранируются."""
    return f'<font name="Mono" size="8.8" color="#0F172A">{escape(text)}</font>'


def draw_text(c, x, y, text, font, size, align="left"):
    """Нарисовать строку на холсте; стрелки - шрифтом Mono, остальное - font."""
    parts = re.split(f"([{ARROWS}])", text)
    fonts = ["Mono" if part in ARROWS and part else font for part in parts]
    widths = [
        pdfmetrics.stringWidth(part, name, size)
        for part, name in zip(parts, fonts, strict=True)
    ]
    total = sum(widths)
    if align == "center":
        x -= total / 2
    elif align == "right":
        x -= total
    for part, name, width in zip(parts, fonts, widths, strict=True):
        c.setFont(name, size)
        c.drawString(x, y, part)
        x += width


# ---------- Примитивы рисования ----------
def rbox(c, x, y, w, h, fill, stroke=None, r=6, lw=1, dash=None):
    """Скруглённый прямоугольник."""
    c.saveState()
    c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(lw)
    if dash:
        c.setDash(dash)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke is not None else 0, fill=1)
    c.restoreState()


def lines_in(
    c, cx, top, width, text, font="PT", size=9, leading=None, color=TEXT, align="center"
):
    """Перенести текст по ширине и нарисовать сверху вниз; вернуть нижнюю y."""
    leading = leading or size * 1.28
    c.saveState()
    c.setFillColor(color)
    y = top - size
    for paragraph in text.split("\n"):
        for line in simpleSplit(paragraph, font, size, width):
            draw_text(c, cx, y, line, font, size, align)
            y -= leading
    c.restoreState()
    return y + leading - size


def node(
    c,
    x,
    y,
    w,
    h,
    title,
    sub="",
    fill=BLUE_L,
    edge=BLUE,
    tsize=10,
    ssize=8,
    dash=None,
    sub_font="PT",
):
    """Блок схемы: заголовок и пояснение по центру."""
    rbox(c, x, y, w, h, fill, edge, r=7, lw=1.1, dash=dash)
    sub_lines = []
    for paragraph in sub.split("\n") if sub else []:
        sub_lines += simpleSplit(paragraph, sub_font, ssize, w - 12)
    title_lines = simpleSplit(title, "PT-Bold", tsize, w - 10)
    total = len(title_lines) * tsize * 1.2 + len(sub_lines) * ssize * 1.3
    if sub_lines:
        total += 3
    top = y + h / 2 + total / 2
    lines_in(c, x + w / 2, top, w - 10, title, "PT-Bold", tsize, tsize * 1.2, INK)
    if sub_lines:
        top -= len(title_lines) * tsize * 1.2 + 3
        lines_in(c, x + w / 2, top, w - 12, sub, sub_font, ssize, ssize * 1.3, MUTED)


def arrow(c, x1, y1, x2, y2, color=MUTED, lw=1.3, head=5.5, dash=None):
    """Линия со стрелкой на конце."""
    import math

    c.saveState()
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(lw)
    if dash:
        c.setDash(dash)
    angle = math.atan2(y2 - y1, x2 - x1)
    ex, ey = x2 - head * 0.9 * math.cos(angle), y2 - head * 0.9 * math.sin(angle)
    c.line(x1, y1, ex, ey)
    c.setDash([])
    path = c.beginPath()
    path.moveTo(x2, y2)
    path.lineTo(x2 - head * math.cos(angle - 0.42), y2 - head * math.sin(angle - 0.42))
    path.lineTo(x2 - head * math.cos(angle + 0.42), y2 - head * math.sin(angle + 0.42))
    path.close()
    c.drawPath(path, fill=1, stroke=0)
    c.restoreState()


def poly_arrow(c, points, color=MUTED, lw=1.3, head=5.5, dash=None):
    """Ломаная со стрелкой на последнем отрезке."""
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    if dash:
        c.setDash(dash)
    for (ax, ay), (bx, by) in zip(points[:-2], points[1:-1], strict=True):
        c.line(ax, ay, bx, by)
    c.restoreState()
    (ax, ay), (bx, by) = points[-2], points[-1]
    arrow(c, ax, ay, bx, by, color, lw, head, dash)


def circle_num(c, x, y, r, text, fill=BLUE, color=WHITE, size=10):
    """Кружок с номером шага."""
    c.saveState()
    c.setFillColor(fill)
    c.circle(x, y, r, stroke=0, fill=1)
    c.setFillColor(color)
    c.setFont("PT-Bold", size)
    c.drawCentredString(x, y - size * 0.35, text)
    c.restoreState()


def chip(c, x, y, text, fill, color, font="Mono", size=7.6, pad=4, h=13):
    """Плашка с текстом; вернуть её ширину."""
    width = pdfmetrics.stringWidth(text, font, size) + pad * 2
    rbox(c, x, y, width, h, fill, None, r=3)
    c.saveState()
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x + pad, y + (h - size) / 2 + 1.2, text)
    c.restoreState()
    return width


class Diagram(Flowable):
    """Блок вёрстки с собственной функцией рисования."""

    def __init__(self, height, draw, width=W):
        """Запомнить размеры и функцию, которая рисует схему."""
        super().__init__()
        self.width, self.height, self.draw_fn = width, height, draw

    def wrap(self, *_):
        """Вернуть занимаемые размеры блока для расчёта страницы."""
        return self.width, self.height

    def draw(self):
        """Нарисовать схему на холсте текущей страницы."""
        self.draw_fn(self.canv, self.width, self.height)


class SectionTitle(Flowable):
    """Номер раздела, заголовок и подзаголовок."""

    def __init__(self, number, title, subtitle, color=BLUE):
        """Запомнить текст и заранее перенести подзаголовок по ширине."""
        super().__init__()
        self.number, self.title, self.subtitle, self.color = (
            number,
            title,
            subtitle,
            color,
        )
        self.sub_lines = simpleSplit(subtitle, "PT", 10.5, W - 46)
        self.height = 36 + len(self.sub_lines) * 14

    def wrap(self, *_):
        """Вернуть занимаемые размеры блока для расчёта страницы."""
        return W, self.height

    def draw(self):
        """Нарисовать номер в цветном квадрате, заголовок и подзаголовок."""
        c = self.canv
        top = self.height
        rbox(c, 0, top - 30, 34, 30, self.color, None, r=7)
        c.setFillColor(WHITE)
        c.setFont("PT-Bold", 15)
        c.drawCentredString(17, top - 21, self.number)
        c.setFillColor(INK)
        c.setFont("PT-Bold", 21)
        c.drawString(46, top - 22, self.title)
        c.setFillColor(MUTED)
        y = top - 40
        for line in self.sub_lines:
            draw_text(c, 46, y, line, "PT", 10.5)
            y -= 14


def callout(text, color=BLUE, fill=BLUE_L, style=BODY_S):
    """Выделенный блок с цветной полосой слева."""
    table = Table([[p(text, style)]], colWidths=[W])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("LINEBEFORE", (0, 0), (0, -1), 3.5, color),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def code_block(text, width=W):
    """Блок кода или команд моноширинным шрифтом на светлом фоне."""
    table = Table([[Preformatted(text.rstrip("\n"), CODE)]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def grid_table(rows, widths, head_fill=INK, zebra=True, styles=None):
    """Таблица с тёмной шапкой и полосами."""
    table = Table(rows, colWidths=widths, repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), head_fill),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if zebra:
        for index in range(1, len(rows)):
            if index % 2 == 0:
                commands.append(("BACKGROUND", (0, index), (-1, index), SOFT))
    table.setStyle(TableStyle(commands + (styles or [])))
    return table


def simple_table(headers, rows, widths, styles=None):
    """Таблица из строк с разметкой: первая колонка жирная, остальные обычные.

    styles задаёт стиль абзаца для каждой колонки (по умолчанию CELL_B, CELL...).
    """
    styles = styles or [CELL_B] + [CELL] * (len(headers) - 1)
    prepared = [[p(value, HEAD) for value in headers]]
    for row in rows:
        prepared.append(
            [p(value, style) for value, style in zip(row, styles, strict=True)]
        )
    return grid_table(prepared, widths)


def cards(items, columns=3, gap=10):
    """Ряд карточек: (заголовок, текст, цвет, светлый цвет)."""
    width = (W - gap * (columns - 1)) / columns
    cells = []
    for title, text, color, fill in items:
        hex_color = color.hexval().replace("0x", "#")
        inner = Table(
            [
                [
                    p(
                        f'<font color="{hex_color}"><b>{title}</b></font>',
                        ParagraphStyle("ct", parent=BODY, fontSize=10.5, leading=13),
                    )
                ],
                [p(text, ParagraphStyle("cb", parent=BODY, fontSize=9, leading=12.6))],
            ],
            colWidths=[width],
        )
        inner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), fill),
                    ("LINEABOVE", (0, 0), (-1, 0), 3, color),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        cells.append(inner)
    rows = [cells[i : i + columns] for i in range(0, len(cells), columns)]
    widths = []
    for _ in range(columns):
        widths += [width, gap]
    grid_rows = []
    for row in rows:
        line = []
        for cell in row:
            line += [cell, ""]
        while len(line) < columns * 2:
            line += ["", ""]
        grid_rows.append(line[:-1])
    table = Table(grid_rows, colWidths=widths[:-1])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), gap),
            ]
        )
    )
    return table


def stat_tiles(c, x, y, w, h, items, fill, value_color, label_color, edge=None):
    """Ряд плиток «число + подпись»."""
    gap = 8
    width = (w - gap * (len(items) - 1)) / len(items)
    for index, (value, label) in enumerate(items):
        left = x + index * (width + gap)
        rbox(c, left, y, width, h, fill, edge, r=8, lw=0.8)
        c.setFillColor(value_color)
        c.setFont("PT-Bold", 22)
        c.drawCentredString(left + width / 2, y + h - 30, value)
        lines_in(
            c,
            left + width / 2,
            y + h - 38,
            width - 12,
            label,
            "PT",
            8.4,
            10.6,
            label_color,
        )


# ---------- Данные проекта ----------
def read_source(relative):
    """Прочитать файл проекта, чтобы PDF показывал настоящий код."""
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def function_source(relative, name):
    """Вернуть исходник функции вместе с декораторами по её имени."""
    source = read_source(relative)
    for item in ast.walk(ast.parse(source)):
        if isinstance(item, ast.FunctionDef) and item.name == name:
            first = min([item.lineno] + [d.lineno for d in item.decorator_list])
            return "\n".join(source.splitlines()[first - 1 : item.end_lineno])
    raise ValueError(f"Функция {name} не найдена в {relative}")


def locked_dependencies():
    """Сопоставить прямые зависимости из pyproject.toml с версиями из uv.lock."""
    project = tomllib.loads(read_source("pyproject.toml"))
    lock = tomllib.loads(read_source("uv.lock"))
    versions = {item["name"]: item["version"] for item in lock["package"]}

    def name_of(spec):
        """Имя пакета без extras и ограничений версии."""
        return re.split(r"[\[<>=!~ ;]", spec, maxsplit=1)[0].lower()

    direct = [(name_of(spec), "runtime") for spec in project["project"]["dependencies"]]
    for spec in project["dependency-groups"]["dev"]:
        direct.append((name_of(spec), "dev"))
    rows = [(name, versions[name], group) for name, group in direct]
    # Две библиотеки, на которых стоит FastAPI: их версии тоже важно знать.
    rows += [
        (name, versions[name], "через fastapi") for name in ("starlette", "pydantic")
    ]
    return rows, len(lock["package"])


# ---------- Колонтитулы ----------
def cover_page(c, doc):
    """Обложка рисуется целиком на холсте."""
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
        left, PAGE_H - 92, "УЧЕБНЫЙ ПРОЕКТ № 2  ·  ВЫМЫШЛЕННАЯ КОМПАНИЯ INDUSTRIALFLOW"
    )
    c.setFillColor(WHITE)
    c.setFont("PT-Bold", 44)
    c.drawString(left, PAGE_H - 150, "AI Data Analyst")
    c.setFillColor(HEX("#FDBA74"))
    c.setFont("PT-Bold", 17)
    c.drawString(left, PAGE_H - 180, "Этап 01 · Подготовка проекта")
    c.setFont("PT", 14)
    c.setFillColor(HEX("#CBD5E1"))
    y = PAGE_H - 208
    for line in simpleSplit(
        "Наглядное руководство: окружение uv, первый API на FastAPI, настройки, "
        "тесты, проверки качества и CI. Всё, на что лягут база данных, "
        "аналитика и AI-агент.",
        "PT",
        14,
        W - 30,
    ):
        c.drawString(left, y, line)
        y -= 19

    # Мини-схема пути запроса.
    steps = [
        ("Браузер", "curl или /docs"),
        ("Uvicorn", "сервер :8000"),
        ("FastAPI", "маршрут /health"),
        ("Pydantic", "проверка ответа"),
        ("JSON", '{"status":"ok"}'),
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
        "Числа в будущих отчётах считает код. Сегодня — фундамент для этого кода.",
    )

    tests = verification["tests"]
    checks = verification["checks"]
    passed_checks = sum(1 for item in checks if item["status"] == "pass")
    stat_tiles(
        c,
        MARGIN,
        342,
        W,
        74,
        [
            ("1 / 10", "этап курса завершён"),
            (f"{tests['passed']} / {tests['total']}", "автотестов прошли"),
            (f"{passed_checks} / {len(checks)}", "локальных проверок PASS"),
            (str(doc.lock_packages), "пакетов зафиксировано в uv.lock"),
            ("1", "маршрут API: GET /health"),
        ],
        HEX("#1E293B"),
        WHITE,
        HEX("#94A3B8"),
        HEX("#334155"),
    )
    c.setFillColor(HEX("#CBD5E1"))
    c.setFont("PT-Bold", 10)
    c.drawString(MARGIN, 300, "Что внутри")
    c.setFont("PT", 9.5)
    c.setFillColor(HEX("#94A3B8"))
    for index, item in enumerate(CONTENTS):
        column, row = divmod(index, 8)
        c.drawString(MARGIN + column * 250, 282 - row * 15, f"{index + 1}  {item}")
    c.setStrokeColor(HEX("#334155"))
    c.line(MARGIN, 82, PAGE_W - MARGIN, 82)
    c.setFillColor(HEX("#64748B"))
    c.setFont("PT", 8.6)
    environment = verification["environment"]
    c.drawString(
        MARGIN,
        66,
        f"Проверка {verification['checked_at']} · коммит "
        f"{verification['base_commit']} · uv {environment['uv']} · "
        f"Python {environment['python']} · {environment['os']}",
    )
    c.drawString(
        MARGIN,
        53,
        "Подробный текст этапа — docs/STAGE_01.md; журнал и отчёт — "
        "docs/DEVELOPMENT_LOG.md, docs/VERIFICATION.md",
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
    c.drawString(MARGIN, 9 * mm, "AI Data Analyst · этап 01 · наглядное руководство")
    c.drawRightString(PAGE_W - MARGIN, 9 * mm, str(doc.page))
    c.restoreState()


# ---------- Схемы ----------
ROADMAP = [
    "Подготовка проекта",
    "PostgreSQL и схема БД",
    "Генерация данных",
    "Аналитическое ядро",
    "Поиск аномалий",
    "REST API",
    "AI-агент",
    "Интерфейс и отчёты",
    "Тесты и безопасность",
    "Docker и публикация",
]


def roadmap(c, w, h):
    """Десять этапов курса: первый готов, второй следующий."""
    gap, bh, row_gap = 9, 50, 12
    bw = (w - 4 * gap) / 5
    for index, title in enumerate(ROADMAP):
        row, column = divmod(index, 5)
        x = column * (bw + gap)
        y = h - bh - row * (bh + row_gap)
        if index == 0:
            fill, edge, color, status = GREEN_L, GREEN, GREEN, "готово"
        elif index == 1:
            fill, edge, color, status = BLUE_L, BLUE, BLUE, "далее"
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
        ("Клиент", "браузер, curl\nили Swagger /docs", ORANGE_L, ORANGE),
        ("Uvicorn", "слушает\n127.0.0.1:8000", TEAL_L, TEAL),
        ("FastAPI", "ищет маршрут\nGET /health", BLUE_L, BLUE),
        ("health()", "возвращает\nHealthResponse", VIOLET_L, VIOLET),
        ("Pydantic", "проверяет схему\nи пишет JSON", GREEN_L, GREEN),
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
        w / 2, top_y + 5, 'ответ: HTTP 200 · application/json · {"status":"ok"}'
    )
    # TestClient входит сразу в FastAPI, минуя сеть и Uvicorn.
    fx = 2 * (bw + gap) + bw / 2
    node(
        c,
        fx - 95,
        4,
        190,
        42,
        "TestClient в тестах",
        "вызывает приложение напрямую:\nбез сети и без Uvicorn",
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
        ("pyproject.toml", "что нужно проекту:\nfastapi>=0.142.2", BLUE_L, BLUE),
        ("uv.lock", "точные версии и хэши\nвсех пакетов", VIOLET_L, VIOLET),
        (".venv", "Python 3.12.15\nи установленные пакеты", TEAL_L, TEAL),
        ("uv run …", "uvicorn, pytest,\nruff, mypy", GREEN_L, GREEN),
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
    labels = [("в Git", GREEN), ("в Git", GREEN), ("не в Git", ORANGE), ("", None)]
    for index, (label, color) in enumerate(labels):
        if label:
            width = pdfmetrics.stringWidth(label, "PT-Bold", 7.6) + 8
            x = index * (bw + gap) + bw / 2 - width / 2
            chip(c, x, y - 20, label, color, WHITE, "PT-Bold", 7.6)


def import_paths(c, w, h):
    """Какие папки видит Python при запуске Uvicorn и pytest."""
    gap = 12
    cw = (w - 2 * gap) / 3
    columns = [
        (
            "uv run uvicorn app.main:app",
            "Uvicorn добавляет текущую папку",
            [
                ("'' = корень проекта", True),
                (".../lib/python3.12", False),
                (".../site-packages", False),
            ],
            ("import app: найден", GREEN),
        ),
        (
            "uv run pytest",
            "без настройки pythonpath",
            [
                ("tests/  (папка теста)", False),
                (".venv/bin", False),
                (".../lib/python3.12", False),
                (".../site-packages", False),
            ],
            ("ModuleNotFoundError", ORANGE),
        ),
        (
            "uv run pytest",
            'с pythonpath = ["."]',
            [
                ("корень проекта ← pythonpath", True),
                ("tests/", False),
                (".venv/bin", False),
                ("stdlib, site-packages", False),
            ],
            ("import app: найден", GREEN),
        ),
    ]
    for index, (title, sub, entries, (result, color)) in enumerate(columns):
        x = index * (cw + gap)
        rbox(c, x, 0, cw, h, SOFT, LINE, r=8, lw=0.8)
        c.setFillColor(INK)
        draw_text(c, x + cw / 2, h - 18, title, "Mono-Bold", 7.8, "center")
        c.setFillColor(MUTED)
        draw_text(c, x + cw / 2, h - 31, sub, "PT", 8.4, "center")
        c.setFillColor(MUTED)
        draw_text(c, x + 10, h - 50, "sys.path:", "PT-Bold", 7.8)
        y = h - 74
        for text, found in entries:
            fill, edge = (GREEN_L, GREEN) if found else (WHITE, LINE)
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
    panels = [
        (
            "Запрос клиента",
            BLUE,
            [
                ("строка запроса", "GET /health HTTP/1.1"),
                ("заголовки", "host: 127.0.0.1:8000"),
                ("", "accept: */*"),
                ("тело", "нет: GET только читает"),
            ],
        ),
        (
            "Ответ сервера",
            GREEN,
            [
                ("строка статуса", "HTTP/1.1 200 OK"),
                ("заголовки", "content-type: application/json"),
                ("", "content-length: 15"),
                ("тело", '{"status":"ok"}'),
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
            font = "PT-Italic" if tag == "тело" and index == 0 else "Mono"
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
        ("Ошибка в коде", 'health() возвращает\n{"status": "fail"}', ORANGE_L, ORANGE),
        ("mypy: до запуска", "Incompatible return\nvalue type", VIOLET_L, VIOLET),
        (
            "FastAPI: при запросе",
            "ResponseValidationError:\nInput should be 'ok'",
            BLUE_L,
            BLUE,
        ),
        ("Клиент", "500 Internal Server Error\nвместо неверных данных", AMBER_L, AMBER),
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
        ("Переменная окружения", "APP_NAME=... uv run uvicorn ...", BLUE_L, BLUE),
        ("Файл .env", 'APP_NAME="..."  (файл не в Git)', TEAL_L, TEAL),
        ("Значение по умолчанию", 'app_name = "AI Data Analyst"', SLATE_L, MUTED),
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
    c.drawCentredString(0, 0, "важнее")
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
        "settings.app_name",
        "первый источник, где\nзначение задано",
        GREEN_L,
        GREEN,
        tsize=9.6,
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
            "pytest находит тест",
            "test_health_returns_ok\n(client: TestClient)",
            SLATE_L,
            MUTED,
        ),
        ("Код до yield", "with TestClient(app)\nоткрывает клиент", TEAL_L, TEAL),
        ("Сам тест", "client.get('/health')\nи проверки assert", BLUE_L, BLUE),
        (
            "Код после yield",
            "with закрывает клиент,\nдаже если тест упал",
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


def ci_pipeline(c, w, h):
    """Задание CI: когда запускается и какие шаги выполняет по порядку."""
    c.setFillColor(INK)
    draw_text(c, 0, h - 11, "Запуск:", "PT-Bold", 9)
    x = 46
    for label in ("push в main", "pull request в main", "вручную: workflow_dispatch"):
        x += chip(c, x, h - 15, label, ORANGE_L, ORANGE, "PT-Bold", 7.8, 6, 15) + 6
    panel_top = h - 26
    rbox(c, 0, 0, w, panel_top, SOFT, LINE, r=8, lw=0.8)
    c.setFillColor(MUTED)
    draw_text(
        c,
        10,
        panel_top - 15,
        "задание checks · ubuntu-24.04 · не дольше 10 минут",
        "PT-Bold",
        8.4,
    )
    gap, bh = 14, 46
    bw = (w - 20 - 3 * gap) / 4
    row1 = panel_top - 26 - bh
    row2 = row1 - bh - 22
    steps = [
        ("Checkout", "код коммита", BLUE_L, BLUE),
        ("uv 0.12.23", "и Python 3.12", BLUE_L, BLUE),
        ("uv sync --locked", "lock = pyproject", VIOLET_L, VIOLET),
        ("Ruff lint", "ruff check .", TEAL_L, TEAL),
        ("Ruff format", "format --check", TEAL_L, TEAL),
        ("mypy", "strict: app, tests", TEAL_L, TEAL),
        ("pytest", "7 тестов", TEAL_L, TEAL),
        ("Итог", "все шаги PASS:\nзадание зелёное", GREEN_L, GREEN),
    ]
    positions = []
    for index in range(4):
        positions.append((10 + index * (bw + gap), row1))
    for index in range(4):
        positions.append((10 + (3 - index) * (bw + gap), row2))
    for index, ((title, sub, fill, edge), (x, y)) in enumerate(
        zip(steps, positions, strict=True)
    ):
        node(c, x, y, bw, bh, title, sub, fill, edge, tsize=9, ssize=7.6)
        if index < 7:
            circle_num(c, x + 9, y + bh - 9, 6.5, str(index + 1), edge, WHITE, 7.5)
    for index in range(3):
        x, y = positions[index]
        arrow(c, x + bw + 2, y + bh / 2, x + bw + gap - 2, y + bh / 2)
    x, y = positions[3]
    arrow(c, x + bw / 2, y - 2, x + bw / 2, row2 + bh + 2)
    for index in range(4, 7):
        x, y = positions[index]
        arrow(c, x - 2, y + bh / 2, x - gap + 2, y + bh / 2)


def git_flow(c, w, h):
    """Путь изменения от рабочей папки до GitHub и запуска Actions."""
    gap, bh = 58, h - 4
    bw = (w - 3 * gap) / 4
    items = [
        ("Рабочая папка", "файлы, которые\nты изменил", SLATE_L, MUTED),
        ("Индекс", "что войдёт\nв следующий коммит", BLUE_L, BLUE),
        ("Локальная история", "коммиты в папке .git\nна твоём Mac", VIOLET_L, VIOLET),
        ("GitHub", "origin/main;\npush запускает CI", GREEN_L, GREEN),
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


# ---------- Зафиксированные результаты экспериментов ----------
# Пример и вывод получены запуском ruff check с настройками проекта
# на временном файле; длинная последняя строка перенесена для страницы.
RUFF_EXAMPLE = """from app.config import settings
import os
from typing import List


def names(items: List[str], seen=[]) -> List[str]:
    return [item for item in items if item not in seen]"""
RUFF_OUTPUT = """$ uv run ruff check --output-format concise example.py
example.py:1:1: I001 [*] Import block is un-sorted or un-formatted
example.py:1:24: F401 [*] `app.config.settings` imported but unused
example.py:2:8: F401 [*] `os` imported but unused
example.py:3:1: UP035 `typing.List` is deprecated, use `list` instead
example.py:6:18: UP006 [*] Use `list` instead of `List` for type annotation
example.py:6:34: B006 Do not use mutable data structures for argument defaults
example.py:6:41: UP006 [*] Use `list` instead of `List` for type annotation
Found 7 errors.
[*] 5 fixable with the `--fix` option
    (1 hidden fix can be enabled with the `--unsafe-fixes` option)."""
# Вывод mypy из эксперимента раздела 7 (health() возвращала словарь).
MYPY_OUTPUT = """$ uv run mypy app
app/main.py:30: error: Incompatible return value type
    (got "dict[str, str]", expected "HealthResponse")  [return-value]
Found 1 error in 1 file (checked 3 source files)"""


def app_facts():
    """Взять схему HealthResponse и пример JSON из настоящего приложения."""
    # Скрипт запускается как scripts/build_guide.py: корень добавляем явно.
    sys.path.insert(0, str(PROJECT_ROOT))
    from app.main import HealthResponse, app

    schema = app.openapi()["components"]["schemas"]["HealthResponse"]
    return {
        "schema": json.dumps(schema, ensure_ascii=False, indent=2),
        "model_json": HealthResponse(status="ok").model_dump_json(),
    }


def ci_steps_excerpt():
    """Вернуть шаги проверок из ci.yml начиная с установки зависимостей."""
    lines = read_source(".github/workflows/ci.yml").splitlines()
    start = next(i for i, line in enumerate(lines) if "--locked завершает" in line)
    return "\n".join(line[6:] for line in lines[start:])


# ---------- Текст руководства ----------
# Как статус удалённого CI из verification.json звучит в тексте.
REMOTE_LABELS = {
    "not_verified": "не проверен",
    "passed": "задание зелёное",
    "failed": "задание упало",
}
CONTENTS = [
    "Этап за минуту",
    "Путь запроса",
    "Окружение и uv",
    "Создание проекта",
    "Импорт и sys.path",
    "HTTP и JSON",
    "Разбор кода API",
    "Настройки",
    "Тесты",
    "Ruff и mypy",
    "CI на GitHub Actions",
    "Git и GitHub",
    "Шпаргалка команд",
    "Типичные ошибки",
    "Проверь себя",
    "Итоги проверки",
]


def section(story, number, subtitle, color=BLUE):
    """Начать раздел с новой страницы; заголовок берётся из CONTENTS."""
    if len(story) > 2:
        story.append(PageBreak())
    story.append(SectionTitle(str(number), CONTENTS[number - 1], subtitle, color))
    story.append(Spacer(1, 8))


def build_story(verification, dependencies, lock_packages):
    """Собрать все страницы руководства после обложки."""
    story = [NextPageTemplate("content"), PageBreak()]
    tests = verification["tests"]
    facts = app_facts()

    # 1. Этап за минуту
    section(story, 1, "Что уже работает, чего ещё нет и где этот этап в плане курса.")
    story += [
        p(
            "На первом этапе создан каркас будущего ИИ-аналитика компании "
            "<b>IndustrialFlow</b>. Приложение пока умеет одно: отвечать на "
            f"{mono('GET /health')}. Зато вокруг него уже есть всё, что понадобится "
            "дальше: управление зависимостями, настройки, тесты, проверки качества "
            "и CI. Следующие этапы будут добавлять функциональность в этот каркас, "
            "не переделывая его."
        ),
        Spacer(1, 10),
        cards(
            [
                (
                    "API",
                    "FastAPI-приложение с маршрутом GET /health и Pydantic-"
                    "моделью ответа. Документация /docs строится сама.",
                    BLUE,
                    BLUE_L,
                ),
                (
                    "Настройки",
                    "Класс Settings читает параметры из переменных "
                    "окружения и .env. Пароли и ключи не попадут в код.",
                    TEAL,
                    TEAL_L,
                ),
                (
                    "Тесты",
                    f"{tests['total']} тестов pytest: HTTP-ответы, OpenAPI, "
                    "приоритет настроек, совпадение версий. Все проходят.",
                    GREEN,
                    GREEN_L,
                ),
                (
                    "Качество",
                    "Ruff проверяет стиль, ошибки и импорты и форматирует "
                    "код. mypy в строгом режиме проверяет типы.",
                    VIOLET,
                    VIOLET_L,
                ),
                (
                    "CI",
                    "GitHub Actions повторяет все проверки на чистой Linux-"
                    "машине при каждом push и pull request.",
                    ORANGE,
                    ORANGE_L,
                ),
                (
                    "Воспроизводимость",
                    f"uv.lock фиксирует версии {lock_packages} "
                    "пакетов; берутся только выпуски старше двух недель.",
                    AMBER,
                    AMBER_L,
                ),
            ]
        ),
        p("Где мы в плане курса", H2),
        Diagram(114, roadmap),
        Spacer(1, 12),
        callout(
            "<b>Чего ещё нет:</b> базы данных, демонстрационных данных, аналитики "
            "и LLM — это этапы 02–07. Сейчас важно понять цепочку «запрос → "
            "сервер → приложение → ответ» и инструменты, которые будут проверять "
            "каждый следующий шаг.",
            AMBER,
            AMBER_L,
        ),
        p("Главный принцип проекта", H2),
        callout(
            "<b>Числа считает код, а не LLM.</b> Выручку, средний чек, сравнения "
            "периодов и аномалии всегда рассчитывает детерминированный SQL или "
            "Python. Модель понимает вопрос, выбирает инструменты и объясняет "
            "результат. Поэтому с первого этапа так важны тесты и проверки: каждое "
            "число в будущем отчёте должно быть подтверждено кодом, который "
            "проверен автоматически.",
        ),
    ]

    # 2. Путь запроса
    section(
        story,
        2,
        'Что происходит между нажатием Execute в /docs и ответом {"status": "ok"}.',
        TEAL,
    )
    story += [
        Diagram(186, request_flow),
        Spacer(1, 12),
        simple_table(
            ["Шаг", "Кто", "Что делает"],
            [
                [
                    "1",
                    "Клиент",
                    "Формирует HTTP-запрос GET /health и отправляет "
                    "его на 127.0.0.1:8000.",
                ],
                [
                    "2",
                    "Uvicorn",
                    "Принимает соединение, разбирает HTTP и передаёт "
                    "запрос приложению по протоколу ASGI.",
                ],
                [
                    "3",
                    "FastAPI",
                    "Ищет обработчик по паре «метод + путь». Для POST "
                    "ответит 405, для неизвестного пути — 404.",
                ],
                ["4", "health()", 'Создаёт объект HealthResponse(status="ok").'],
                [
                    "5",
                    "Pydantic",
                    "Проверяет объект по схеме ответа и превращает его в JSON.",
                ],
            ],
            [34, 72, W - 106],
        ),
        p("Фактический ответ сервера", H2),
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
            "<b>TestClient</b> в тестах подключается сразу к FastAPI (шаг 3): без "
            "сети, без Uvicorn и без свободного порта. Поэтому все тесты проходят "
            f"за {tests['seconds']} с.",
            TEAL,
            TEAL_L,
        ),
    ]

    # 3. Окружение и uv
    section(
        story,
        3,
        "Как uv превращает список требований в одинаковое окружение на любом "
        "компьютере.",
        VIOLET,
    )
    dependency_purpose = {
        "fastapi": "маршруты, проверка данных, /docs",
        "pydantic-settings": "настройки из окружения и .env",
        "uvicorn": "ASGI-сервер, слушает порт",
        "httpx2": "HTTP-клиент для TestClient",
        "mypy": "проверка типов",
        "pytest": "запуск тестов",
        "ruff": "линтер и форматировщик",
        "starlette": "веб-основа FastAPI",
        "pydantic": "модели и проверка данных",
    }
    story += [
        Diagram(98, uv_flow),
        Spacer(1, 10),
        p(
            "<b>Виртуальное окружение</b> " + mono(".venv") + " — отдельная папка "
            "со своим Python и библиотеками только для этого проекта. Так проекты "
            "не мешают друг другу. Системный " + mono("python3") + " на этом Mac — "
            "3.9.6; его не трогаем, всё запускаем через " + mono("uv run") + ".",
            BODY_S,
        ),
        Spacer(1, 8),
        simple_table(
            ["", "pyproject.toml", "uv.lock"],
            [
                ["Кто пишет", "Человек и команда uv add", "Только uv"],
                [
                    "Что внутри",
                    "Требования: fastapi&gt;=0.142.2",
                    "Точные версии и хэши файлов",
                ],
                [
                    "Транзитивные пакеты",
                    "Нет",
                    f"Да, все {lock_packages}: starlette, pydantic, anyio…",
                ],
                ["В Git", "Да", "Да"],
            ],
            [110, (W - 110) / 2, (W - 110) / 2],
        ),
        p("Зависимости проекта (версии из uv.lock)", H2),
        simple_table(
            ["Пакет", "Версия", "Группа", "Зачем"],
            [
                [mono(name), mono(version), group, dependency_purpose.get(name, "")]
                for name, version, group in dependencies
            ],
            [118, 70, 84, W - 272],
            [CELL, CELL, CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            "<b>Политика возраста пакетов.</b> "
            + mono('[tool.uv] exclude-newer = "2026-10-06T00:00:00Z"')
            + " — uv не видит выпуски PyPI новее этой "
            "даты. Свежий выпуск бывает сломан или даже вредоносен; за две недели "
            "такие проблемы обычно находят. Самый новый пакет в lock — "
            "websockets 17.2 от 3 октября.",
            VIOLET,
            VIOLET_L,
        ),
    ]

    # 4. Создание проекта
    section(
        story,
        4,
        "Какими командами создан проект, чем они отличаются от стартового задания "
        "и что лежит в каждой папке.",
        ORANGE,
    )
    story += [
        code_block(
            "# uv 0.12.23 — та же версия, что закреплена в CI\n"
            "curl -LsSf https://astral.sh/uv/0.12.23/install.sh \\\n"
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
                    "uv init в uv 0.12",
                    "Без флагов создаёт пакет-библиотеку: "
                    "src/ai_data_analyst/, [build-system] и [project.scripts]. Для "
                    "веб-сервиса с папкой app/ в корне нужен --app --no-package.",
                    ORANGE,
                    ORANGE_L,
                ),
                (
                    "httpx2 вместо httpx",
                    "Starlette 1.7 предупреждает: «Using httpx "
                    "with starlette.testclient is deprecated; install httpx2 instead». "
                    "TestClient теперь работает на httpx2.",
                    ORANGE,
                    ORANGE_L,
                ),
            ],
            columns=2,
        ),
        p("Карта файлов", H2),
        simple_table(
            ["Файл или папка", "Для чего нужен"],
            [
                [
                    mono("app/__init__.py"),
                    'Делает app пакетом; хранит версию __version__ = "0.1.0".',
                ],
                [mono("app/config.py"), "Класс Settings и готовый объект settings."],
                [mono("app/main.py"), "Объект FastAPI и маршрут GET /health."],
                [mono("tests/"), "Три файла тестов: API, настройки, версия."],
                [
                    mono("pyproject.toml"),
                    "Описание проекта, зависимости и настройки pytest, Ruff, mypy, uv.",
                ],
                [mono("uv.lock"), f"Точные версии всех {lock_packages} пакетов."],
                [mono(".python-version"), "3.12 — какой Python выбирает uv."],
                [
                    mono(".env.example"),
                    "Образец локальных настроек; сам .env — не в Git.",
                ],
                [mono(".gitignore"), "Что Git не отслеживает: .venv, кеши, .env."],
                [mono(".github/workflows/ci.yml"), "Проверки в GitHub Actions."],
                [
                    mono("docs/instructions/"),
                    "Короткие английские инструкции: запуск, API, проверки, CI, "
                    "структура.",
                ],
                [
                    mono("docs/"),
                    "Руководство этапа, CI/CD, подход и ADR, журнал, отчёт, этот PDF.",
                ],
                [mono("scripts/build_guide.py"), "Сборка этого PDF."],
                [mono("AGENTS.md"), "Правила работы над проектом."],
            ],
            [160, W - 160],
            [CELL, CELL],
        ),
    ]

    # 5. Импорт и sys.path
    section(
        story,
        5,
        "Почему сервер находит пакет app, а pytest без настройки — нет.",
        BLUE,
    )
    story += [
        p(
            "<b>Модуль</b> — один файл " + mono(".py") + ". <b>Пакет</b> — папка с "
            "модулями; файл " + mono("__init__.py") + " выполняется при первом "
            "импорте пакета. <b>sys.path</b> — список папок, где Python ищет модули. "
            "Строка " + mono("from app.main import app") + " работает, только если "
            "в одной из этих папок лежит папка app.",
            BODY_S,
        ),
        Spacer(1, 10),
        Diagram(178, import_paths),
        Spacer(1, 10),
        p("Фактическая ошибка до настройки", H2),
        code_block(
            "$ uv run pytest\n"
            "ImportError while importing test module '.../tests/test_health.py'.\n"
            "E   ModuleNotFoundError: No module named 'app'\n"
            "Interrupted: 3 errors during collection"
        ),
        p("Исправление в pyproject.toml", H2),
        code_block(
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["."]'
        ),
        Spacer(1, 10),
        callout(
            "<b>Почему так.</b> Проект создан с --no-package: в .venv ставятся "
            "только зависимости, сам app не устанавливается. Другие решения — "
            "запускать python -m pytest (флаг -m добавляет текущую папку) или "
            "оформить проект пакетом. Явная настройка работает при любом способе "
            "запуска.",
        ),
    ]

    # 6. HTTP и JSON
    http_facts = {item["request"]: item["status"] for item in verification["http"]}
    section(
        story,
        6,
        "Из чего состоят запрос и ответ и какие коды встретятся в проекте.",
        TEAL,
    )
    story += [
        Diagram(132, http_anatomy),
        Spacer(1, 12),
        simple_table(
            ["Метод", "Смысл", "В этом проекте"],
            [
                [
                    mono("GET"),
                    "Получить данные, ничего не меняя",
                    "GET /health; позже GET /api/metrics/revenue",
                ],
                [
                    mono("POST"),
                    "Создать объект или запустить действие",
                    "позже — вопрос AI-агенту",
                ],
                [
                    mono("PUT / PATCH"),
                    "Заменить или частично изменить",
                    "пока не используем",
                ],
                [mono("DELETE"), "Удалить", "пока не используем"],
            ],
            [86, 190, W - 276],
        ),
        Spacer(1, 10),
        simple_table(
            ["Код", "Значение", "Когда увидишь (проверено)"],
            [
                ["200 OK", "Успех", f"GET /health → {http_facts['GET /health']}"],
                [
                    "404 Not Found",
                    "Такого пути нет",
                    f"GET /nope → {http_facts['GET /nope']}",
                ],
                [
                    "405 Method Not Allowed",
                    "Путь есть, метод не тот",
                    f"POST /health → {http_facts['POST /health']}, "
                    "заголовок allow: GET",
                ],
                [
                    "422 Unprocessable Content",
                    "Неверные входные данные",
                    "появится на этапе 06 с параметрами запросов",
                ],
                [
                    "500 Internal Server Error",
                    "Ошибка на сервере",
                    "эксперимент в разделе 7",
                ],
            ],
            [140, 130, W - 270],
        ),
        Spacer(1, 10),
        p(
            "<b>JSON</b> — текстовый формат данных: объекты {...}, массивы [...], "
            "строки, числа, true / false / null. FastAPI превращает Pydantic-модель "
            "в JSON сам, а " + mono("response.json()") + " в тесте превращает JSON "
            "обратно в словарь Python.",
            BODY_S,
        ),
    ]

    # 7. Разбор кода API
    section(story, 7, "app/main.py построчно и эксперимент с неправильным ответом.")
    story += [
        code_block(read_source("app/main.py")),
        Spacer(1, 10),
        simple_table(
            ["Фрагмент", "Что делает"],
            [
                [
                    mono("import ..."),
                    "Три группы: стандартная библиотека, сторонние "
                    "пакеты, наш код. Порядок проверяет правило Ruff I.",
                ],
                [
                    mono("app = FastAPI(...)"),
                    "Объект приложения. Его находит Uvicorn "
                    "(app.main:app) и вызывает TestClient. title и version — в /docs.",
                ],
                [
                    mono("class HealthResponse"),
                    "Pydantic-модель: описание формы "
                    'ответа. Literal["ok"] разрешает ровно одно значение.',
                ],
                [
                    mono('@app.get("/health")'),
                    "Регистрирует функцию для пары "
                    "GET + /health. Другие методы на этом пути получат 405.",
                ],
                [
                    mono("-> HealthResponse"),
                    "Аннотация возврата становится схемой "
                    "ответа: по ней строится /docs и проверяется результат функции.",
                ],
                [
                    mono("def, не async def"),
                    "Обычную функцию FastAPI выполняет в "
                    "отдельном потоке. К async вернёмся на этапе 06.",
                ],
            ],
            [150, W - 150],
            [CELL, CELL],
        ),
    ]
    # Вторая страница раздела: эксперимент, превращение в JSON и OpenAPI.
    story += [
        PageBreak(),
        p("Эксперимент: неправильный ответ", H2),
        p(
            "Во временной копии проекта функция health() вернула "
            + mono('{"status": "fail"}')
            + ". Фактические результаты:",
            BODY_S,
        ),
        Spacer(1, 8),
        Diagram(80, validation_levels),
        Spacer(1, 10),
        callout(
            "<b>Два уровня защиты:</b> типы ловят ошибку в коде, Pydantic — "
            "в данных. Неправильный ответ не уходит клиенту молча. Для "
            "аналитики это главное: лучше явная ошибка, чем неверное число "
            "в отчёте.",
            GREEN,
            GREEN_L,
        ),
        p("Модель → JSON → словарь", H2),
        p(
            "FastAPI превращает объект модели в JSON-текст, а тест превращает "
            "JSON обратно в словарь Python. Значения ниже получены из настоящего "
            "приложения при сборке PDF:",
            BODY_S,
        ),
        Spacer(1, 6),
        code_block(
            '>>> HealthResponse(status="ok").model_dump_json()   # модель → JSON\n'
            f"'{facts['model_json']}'\n"
            '>>> client.get("/health").json()                    # JSON → dict\n'
            "{'status': 'ok'}"
        ),
        p("OpenAPI и страница /docs", H2),
        p(
            "FastAPI собирает описание всех маршрутов и моделей в документ OpenAPI "
            "(" + mono("GET /openapi.json") + "). Страница /docs — это Swagger UI, "
            "который рисует этот документ. Схема HealthResponse из приложения; "
            "docstring модели стал полем description:",
            BODY_S,
        ),
        Spacer(1, 6),
        code_block(facts["schema"]),
    ]

    # 8. Настройки
    section(story, 8, "Конфигурация живёт в окружении, а не в коде.", TEAL)
    story += [
        Diagram(140, settings_priority),
        Spacer(1, 10),
        code_block(read_source("app/config.py")),
        Spacer(1, 10),
        simple_table(
            ["Тест", "Что закрепляет"],
            [
                [
                    mono("test_default_app_name"),
                    "Без окружения и .env берётся значение из кода.",
                ],
                [
                    mono("test_env_file_overrides_default"),
                    "Строка в .env заменяет значение по умолчанию.",
                ],
                [
                    mono("test_environment_variable_beats_env_file"),
                    "Переменная окружения важнее строки в .env.",
                ],
            ],
            [230, W - 230],
            [CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            '<b>extra="ignore"</b> — позже в .env появятся переменные Docker и '
            "PostgreSQL, не относящиеся к Settings. <b>settings = Settings()</b> "
            "создаётся один раз при импорте, поэтому изменения .env видны только "
            "после перезапуска сервера: --reload следит за .py-файлами.",
            TEAL,
            TEAL_L,
        ),
        Spacer(1, 8),
        code_block('APP_NAME="IndustrialFlow Analytics" uv run uvicorn app.main:app'),
        p("Заголовок страницы /docs сменится на «IndustrialFlow Analytics».", SMALL),
    ]

    # 9. Тесты
    section(
        story,
        9,
        "Как pytest находит тесты, что такое фикстура и что доказывает каждый тест.",
        GREEN,
    )
    story += [
        p(
            "Pytest находит файлы " + mono("test_*.py") + " в папке tests/ и "
            "выполняет функции с именем " + mono("test_...") + ". Внутри обычный "
            "assert: если условие ложно, pytest покажет, какие значения не "
            "совпали. Фикстура — подготовка для теста; тест получает её, объявив "
            "параметр с тем же именем.",
            BODY_S,
        ),
        Spacer(1, 8),
        Diagram(68, fixture_flow),
        Spacer(1, 10),
        code_block(function_source("tests/test_health.py", "client")),
        Spacer(1, 10),
        simple_table(
            ["Тест", "Что доказывает"],
            [
                [
                    mono("test_health_returns_ok"),
                    'GET /health → 200 и ровно {"status": "ok"}',
                ],
                [mono("test_health_rejects_post"), "POST /health → 405"],
                [
                    mono("test_openapi_describes_health"),
                    "Схема знает версию, путь и обязательное поле status",
                ],
                [mono("test_default_app_name"), "Умолчание из кода"],
                [mono("test_env_file_overrides_default"), ".env важнее умолчания"],
                [
                    mono("test_environment_variable_beats_env_file"),
                    "Окружение важнее .env",
                ],
                [
                    mono("test_version_matches_pyproject"),
                    "app.__version__ совпадает с pyproject.toml",
                ],
            ],
            [230, W - 230],
            [CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            "Встроенные фикстуры: <b>monkeypatch</b> временно меняет переменные "
            "окружения и всё возвращает; <b>tmp_path</b> даёт новую пустую папку. "
            "Каждый тест — «подготовка → действие → проверка», части разделены "
            "пустыми строками.",
            GREEN,
            GREEN_L,
        ),
    ]

    # 10. Ruff и mypy
    section(
        story,
        10,
        "Два инструмента, которые находят ошибки до запуска программы.",
        VIOLET,
    )
    story += [
        simple_table(
            ["Правило Ruff", "Что ищет"],
            [
                [mono("E"), "Нарушения стиля PEP 8"],
                [mono("F"), "Ошибки: неиспользуемые импорты, неопределённые имена"],
                [mono("I"), "Порядок импортов"],
                [mono("UP"), "Устаревший синтаксис, который в Python 3.12 проще"],
                [
                    mono("B"),
                    "Типичные ловушки, например изменяемое значение "
                    "аргумента по умолчанию",
                ],
            ],
            [100, W - 100],
            [CELL, CELL],
        ),
        Spacer(1, 10),
        p(
            mono("ruff check .")
            + " ищет проблемы, с "
            + mono("--fix")
            + " исправляет безопасные; "
            + mono("ruff format .")
            + " переформатирует код, а "
            + mono("ruff format --check .")
            + " только проверяет — так в CI. Все команды собраны в шпаргалке "
            "(раздел 13).",
            BODY_S,
        ),
        Spacer(1, 6),
        p(
            "<b>mypy strict</b> требует аннотации у каждой функции и не пропускает "
            "незаметные Any. Плагин " + mono("pydantic.mypy") + " объясняет mypy, "
            "какие аргументы принимают модели и настройки. Пример пользы — "
            "эксперимент из раздела 7: mypy нашёл неверный тип ответа до запуска.",
            BODY_S,
        ),
        Spacer(1, 10),
        callout(
            "<b>Ruff 0.16 форматирует и Python-блоки внутри Markdown.</b> Примеры "
            "кода в docs/STAGE_01.md тоже проходят ruff format --check, поэтому "
            "документация не расходится со стилем кода.",
            VIOLET,
            VIOLET_L,
        ),
        p("Пример: что находит Ruff", H2),
        p(
            "Файл с типичными недочётами проверен с настройками проекта. "
            "Сначала код, затем фактический вывод:",
            BODY_S,
        ),
        Spacer(1, 6),
        code_block(RUFF_EXAMPLE),
        Spacer(1, 6),
        code_block(RUFF_OUTPUT),
        p(
            "I001 — порядок импортов, F401 — неиспользуемый импорт, UP035 и UP006 — "
            "List вместо list, B006 — общий список по умолчанию, который будет "
            "копить значения между вызовами. Пометка [*] — Ruff исправит сам "
            "через --fix.",
            SMALL,
        ),
        p("Пример: что находит mypy", H2),
        code_block(MYPY_OUTPUT),
    ]

    # 11. CI
    remote = verification["remote_ci"]
    section(
        story,
        11,
        "Те же проверки на чистой Linux-машине при каждом изменении.",
        ORANGE,
    )
    story += [
        Diagram(190, ci_pipeline),
        Spacer(1, 12),
        simple_table(
            ["Настройка", "Зачем"],
            [
                [
                    mono("permissions: contents: read"),
                    "Заданию разрешено только читать код.",
                ],
                [
                    mono("concurrency"),
                    "Новый push в тот же PR отменяет устаревшую проверку.",
                ],
                [
                    mono("uv sync --locked"),
                    "Ошибка, если uv.lock расходится с pyproject.toml.",
                ],
                [
                    mono("checkout@3d3c42e… # v7.0.1"),
                    "Действия закреплены полным SHA: "
                    "тег автор может перенести на другой код, SHA — нет.",
                ],
                [
                    mono("persist-credentials: false"),
                    "Токен GitHub не остаётся в рабочей папке после checkout.",
                ],
            ],
            [190, W - 190],
            [CELL, CELL],
        ),
        Spacer(1, 10),
        callout(
            f"<b>Статус удалённого CI: {REMOTE_LABELS[remote['status']]}.</b> "
            f"{escape(remote['detail'])}",
            AMBER,
            AMBER_L,
        ),
        p("Шаги проверок в ci.yml", H2),
        code_block(ci_steps_excerpt()),
    ]

    # 12. Git и GitHub
    section(
        story,
        12,
        "Что хранится в репозитории и как опубликовать его на GitHub.",
        BLUE,
    )
    story += [
        Diagram(64, git_flow),
        Spacer(1, 12),
        cards(
            [
                (
                    "В Git",
                    "Код app/ и tests/, pyproject.toml, uv.lock, "
                    ".python-version, .env.example, .gitignore, workflow, "
                    "документация и этот PDF.",
                    GREEN,
                    GREEN_L,
                ),
                (
                    "Не в Git",
                    ".venv (пересоздаётся uv sync), кеши инструментов, "
                    ".env с личными настройками и будущими секретами.",
                    ORANGE,
                    ORANGE_L,
                ),
            ],
            columns=2,
        ),
        p("Коммиты этапа", H2),
        p(
            mono(verification["base_commit"])
            + " — код, тесты, настройки и CI; следующий коммит — руководство, "
            "журнал, отчёт и PDF. История: " + mono("git log --oneline") + ".",
            BODY_S,
        ),
        p("Публикация", H2),
        p(
            "Репозиторий создан: <b>merkertg/ai-data-analyst</b>, оба коммита "
            "этапа отправлены в main. Для нового проекта порядок такой.",
            BODY_S,
        ),
        Spacer(1, 4),
        p(
            "1. На github.com: <b>New repository</b> <b>без</b> README, "
            ".gitignore и лицензии — иначе история на GitHub разойдётся "
            "с локальной.",
            BODY_S,
        ),
        Spacer(1, 4),
        p("2. Подключить удалённый репозиторий и отправить ветку:", BODY_S),
        Spacer(1, 4),
        code_block(
            "git remote add origin git@github.com:<логин>/<репозиторий>.git\n"
            "git push -u origin main"
        ),
        Spacer(1, 6),
        p(
            "3. Открыть вкладку <b>Actions</b>: задание «Lint, types and tests» "
            "должно стать зелёным. Только после этого CI подтверждён.",
            BODY_S,
        ),
        Spacer(1, 10),
        callout(
            "Сообщения коммитов — на английском, в повелительном наклонении: "
            "«Add …», «Fix …». Каждый коммит — законченный шаг, после которого "
            "проходят все проверки.",
        ),
    ]

    # 13. Шпаргалка
    section(story, 13, "Все команды этапа на одной странице.", TEAL)
    commands = [
        ("Создать окружение по lock", "uv sync --locked"),
        ("Запустить сервер", "uv run uvicorn app.main:app --reload"),
        ("Сервер на другом порту", "uv run uvicorn app.main:app --port 8001"),
        ("Проверить ответ", "curl -i http://127.0.0.1:8000/health"),
        ("Документация API", "http://127.0.0.1:8000/docs"),
        ("Все тесты", "uv run pytest"),
        ("Подробно, по одному", "uv run pytest -v"),
        ("Только тесты настроек", "uv run pytest -k config"),
        ("Стоп на первой ошибке", "uv run pytest -x"),
        ("Линтер", "uv run ruff check ."),
        ("Форматирование", "uv run ruff format ."),
        ("Типы", "uv run mypy app tests"),
        ("Добавить библиотеку", "uv add <пакет>"),
        ("Добавить инструмент", "uv add --dev <пакет>"),
        ("Проверить lock", "uv lock --check"),
        ("Прямые зависимости", "uv tree --depth 1"),
        ("Кто занял порт 8000", "lsof -i :8000"),
        ("История коммитов", "git log --oneline"),
        (
            "Пересобрать PDF",
            "uv run --with 'reportlab==4.4.9' python scripts/build_guide.py",
        ),
    ]
    story.append(
        simple_table(
            ["Задача", "Команда"],
            [[task, mono(command)] for task, command in commands],
            [170, W - 170],
        )
    )

    # 14. Типичные ошибки
    section(story, 14, "Симптом, причина и что сделать.", ORANGE)
    errors = [
        (
            mono("uv: command not found"),
            "Терминал открыт до установки uv",
            "Открыть новую вкладку Terminal",
        ),
        (
            mono("ModuleNotFoundError: No module named 'app'"),
            "Нет pythonpath или команда не из корня",
            "Проверить pyproject.toml, выполнить cd в корень проекта",
        ),
        (
            mono("Address already in use"),
            "Порт 8000 занят",
            mono("lsof -i :8000") + " или " + mono("--port 8001"),
        ),
        (mono("405 Method Not Allowed"), "Не тот HTTP-метод", "Для /health — GET"),
        (mono("404 Not Found"), "Опечатка в пути", "Сверить путь с /docs"),
        (
            mono("uv sync --locked") + " завершается ошибкой",
            "pyproject.toml изменён, lock — нет",
            mono("uv lock") + " и закоммитить uv.lock",
        ),
        (
            "Изменения в " + mono(".env") + " не видны",
            "Настройки читаются при старте",
            "Перезапустить сервер",
        ),
        (
            mono("python3 --version") + " → 3.9.6",
            "Это системный Python",
            "Запускать через " + mono("uv run"),
        ),
        (
            "Предупреждение про " + mono("httpx") + " в тестах",
            "Starlette 1.7 ждёт httpx2",
            "Уже исправлено в группе dev",
        ),
        (
            mono("ruff format --check") + " ругается на .md",
            "Python-блок в Markdown не отформатирован",
            mono("uv run ruff format ."),
        ),
    ]
    story.append(
        simple_table(
            ["Симптом", "Причина", "Что сделать"],
            [list(row) for row in errors],
            [190, 145, W - 335],
            [CELL, CELL, CELL],
        )
    )

    # 15. Проверь себя
    section(story, 15, "Вопросы для самопроверки и самостоятельное задание.", VIOLET)
    questions = [
        (
            "Чем pyproject.toml отличается от uv.lock? Почему коммитим оба, а .venv — "
            "нет?",
            "В pyproject.toml — требования к прямым зависимостям, в uv.lock — "
            f"точные версии и хэши всех {lock_packages} пакетов. .venv пересоздаётся "
            "из lock и зависит от платформы.",
        ),
        (
            "Почему Uvicorn находит app, а pytest без настройки — нет?",
            "Uvicorn добавляет текущую папку в sys.path; pytest добавляет tests/, а "
            'проект не установлен как пакет. pythonpath = ["."] добавляет корень.',
        ),
        (
            'Что будет, если health() вернёт {"status": "fail"}?',
            "mypy найдёт ошибку типа до запуска; при запросе FastAPI выбросит "
            "ResponseValidationError, клиент получит 500.",
        ),
        (
            "Чем Uvicorn отличается от FastAPI?",
            "FastAPI — приложение: маршруты, "
            "проверка данных, документация. Uvicorn — сервер: слушает порт и передаёт "
            "запросы приложению по ASGI.",
        ),
        (
            "В каком порядке Settings выбирает app_name?",
            "Переменная окружения → строка в .env → значение по умолчанию.",
        ),
        (
            "Почему действия в CI закреплены SHA, а не тегом v7?",
            "Тег можно переписать на другой код, SHA коммита — нет.",
        ),
    ]
    for index, (question, answer) in enumerate(questions, start=1):
        story += [
            p(f"{index}. {escape(question)}", QUESTION),
            p("Ответ: " + escape(answer), SMALL),
            Spacer(1, 6),
        ]
    story += [
        p("Самостоятельное задание", H2),
        callout(
            "Добавь маршрут <b>GET /version</b>. Ответ описан Pydantic-моделью "
            "VersionResponse: name — из settings.app_name, version — из "
            "app.__version__. Напиши тест на код 200 и тело ответа. Готово, когда "
            "pytest, ruff check, ruff format --check и mypy проходят.",
            VIOLET,
            VIOLET_L,
        ),
        Spacer(1, 6),
        code_block('{"name": "AI Data Analyst", "version": "0.1.0"}'),
        p("Подсказка: маршрут устроен так же, как /health.", SMALL),
    ]

    # 16. Итоги проверки
    environment = verification["environment"]
    section(
        story,
        16,
        f"Что фактически проверено {verification['checked_at']} на коммите "
        f"{verification['base_commit']}.",
        GREEN,
    )
    story += [
        p(
            f"Окружение: {environment['os']}, uv {environment['uv']}, "
            f"Python {environment['python']}. Тесты: {tests['passed']} прошли, "
            f"{tests['failed']} упали, {tests['skipped']} пропущены.",
            BODY_S,
        ),
        Spacer(1, 8),
        simple_table(
            ["Проверка", "Команда", "Результат", "Статус"],
            [
                [
                    escape(item["name"]),
                    mono(item["command"]),
                    escape(item["result"]),
                    '<font color="#15803D"><b>PASS</b></font>'
                    if item["status"] == "pass"
                    else '<font color="#C2410C"><b>FAIL</b></font>',
                ]
                for item in verification["checks"]
            ],
            [78, 170, W - 298, 50],
        ),
        p("Ответы сервера", H2),
        simple_table(
            ["Запрос", "Код", "Тело"],
            [
                [mono(item["request"]), escape(item["status"]), mono(item["body"])]
                for item in verification["http"]
            ],
            [110, 150, W - 260],
        ),
        Spacer(1, 10),
        callout(
            f"<b>GitHub Actions: {REMOTE_LABELS[remote['status']]}.</b> "
            f"{escape(remote['detail'])}",
            AMBER,
            AMBER_L,
        ),
        p("Что дальше", H2),
    ]
    for item in verification["remaining"]:
        story.append(p("• " + escape(item), BODY_S))
        story.append(Spacer(1, 3))
    return story


# ---------- Сборка ----------
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
    for key in ("total", "passed", "failed", "skipped"):
        if type(tests.get(key)) is not int or tests[key] < 0:
            raise ValueError(f"tests.{key}: требуется неотрицательное целое число")
    if tests["passed"] + tests["failed"] + tests["skipped"] != tests["total"]:
        raise ValueError("passed + failed + skipped не равно total")
    for item in data["checks"]:
        if not all(
            isinstance(item.get(key), str) and item[key]
            for key in ("name", "command", "result")
        ) or item.get("status") not in {"pass", "fail"}:
            raise ValueError("Для каждой проверки нужны name, command, result, status")
    for item in data["http"]:
        if not all(isinstance(item.get(key), str) for key in ("request", "status")):
            raise ValueError("Для каждого HTTP-ответа нужны request и status")
    remote = data["remote_ci"]
    if remote.get("status") not in {
        "not_verified",
        "passed",
        "failed",
    } or not isinstance(remote.get("detail"), str):
        raise ValueError("remote_ci: нужны допустимый status и пояснение detail")
    if not isinstance(data["remaining"], list):
        raise ValueError("remaining: требуется список строк")
    return data


def build_guide(output, verification):
    """Сохранить копию старого PDF и заменить его только после успешной сборки."""
    register_fonts()
    dependencies, lock_packages = locked_dependencies()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = Path(tempfile.gettempdir()) / (
            f"ai-data-analyst-guide-before-{stamp}.pdf"
        )
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
            title="AI Data Analyst - этап 01: подготовка проекта",
            author="AI Data Analyst",
            subject="uv, FastAPI, настройки, тесты, Ruff, mypy и CI",
        )
        # Обложка читает эти значения во время отрисовки.
        document.verification = verification
        document.lock_packages = lock_packages
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
        document.build(build_story(verification, dependencies, lock_packages))
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Руководство создано: {output}")


def main(argv=None):
    """Разобрать аргументы и собрать PDF только при явном запуске скрипта."""
    parser = argparse.ArgumentParser(
        description="Собрать русский PDF-гайд AI Data Analyst."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs/guide/ai-data-analyst-guide.pdf",
    )
    parser.add_argument(
        "--verification",
        type=Path,
        default=PROJECT_ROOT / "docs/guide/verification.json",
    )
    args = parser.parse_args(argv)
    build_guide(args.output.resolve(), load_verification(args.verification.resolve()))


if __name__ == "__main__":
    main()
