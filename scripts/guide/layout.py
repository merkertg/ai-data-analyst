"""Вёрстка PDF-гайда: шрифты, цвета, стили текста и общие блоки страниц."""

import re
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, Preformatted, Table, TableStyle

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
