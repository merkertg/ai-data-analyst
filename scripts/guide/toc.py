"""Оглавление PDF-гайда и заголовок раздела с новой страницы."""

from reportlab.platypus import PageBreak, Spacer

from guide.i18n import tr
from guide.layout import BLUE, SectionTitle

# Заголовки разделов (русский, английский). Номер раздела = позиция + 1.
CONTENTS = [
    ("Проект за минуту", "Project in a minute"),
    ("Путь запроса", "Request path"),
    ("Окружение и uv", "Environment and uv"),
    ("Создание проекта", "Creating the project"),
    ("Импорт и sys.path", "Imports and sys.path"),
    ("HTTP и JSON", "HTTP and JSON"),
    ("Разбор кода API", "API code walkthrough"),
    ("Настройки", "Settings"),
    ("Тесты API", "API tests"),
    ("Ruff и mypy", "Ruff and mypy"),
    ("Git и GitHub", "Git and GitHub"),
    ("PostgreSQL в Docker", "PostgreSQL in Docker"),
    ("Таблицы и связи", "Tables and relations"),
    ("Правила целостности", "Integrity rules"),
    ("Деньги и время", "Money and time"),
    ("SQLAlchemy и сессии", "SQLAlchemy and sessions"),
    ("Миграции Alembic", "Alembic migrations"),
    ("/health и /ready", "/health and /ready"),
    ("SQL вручную", "Hand-written SQL"),
    ("Тесты с базой", "Database tests"),
    ("Воспроизводимые данные", "Reproducible data"),
    ("Сценарии A01–A05", "Scenarios A01–A05"),
    ("Загрузка и качество", "Loading and quality"),
    ("Точные показатели", "Exact metrics"),
    ("Месяцы и сравнения", "Months and comparisons"),
    ("Вклады групп", "Group contributions"),
    ("CI на GitHub Actions", "CI on GitHub Actions"),
    ("Шпаргалка команд", "Command cheat sheet"),
    ("Типичные ошибки", "Common errors"),
    ("Проверь себя", "Check yourself"),
    ("Итоги проверки", "Verification results"),
]

# Разделы этапов: на обложке оглавление помечает, к какому этапу они относятся.
STAGE_01_SECTIONS = range(2, 12)
STAGE_02_SECTIONS = range(12, 21)
STAGE_03_SECTIONS = range(21, 24)
STAGE_04_SECTIONS = range(24, 27)


def title(number: int) -> str:
    """Заголовок раздела на текущем языке."""
    ru, en = CONTENTS[number - 1]
    return tr(ru, en)


def section(story: list, number: int, subtitle: str, color=BLUE) -> None:
    """Начать раздел с новой страницы: номер, заголовок и подзаголовок."""
    if len(story) > 2:
        story.append(PageBreak())
    story.append(SectionTitle(str(number), title(number), subtitle, color))
    story.append(Spacer(1, 8))
