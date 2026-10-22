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
    ("Статистические кандидаты", "Statistical candidates"),
    ("Isolation Forest", "Isolation Forest"),
    ("Отдельная оценка сценариев", "Offline scenario evaluation"),
    ("REST API и параметры", "REST API and parameters"),
    ("Сессии и ошибки", "Sessions and errors"),
    ("Сохранённые отчёты", "Saved reports"),
    ("Инструменты агента", "Agent tools"),
    ("Цикл tool calling", "Tool-calling loop"),
    ("Отчёт и доказательства", "Report and evidence"),
    ("Провайдеры и история", "Providers and history"),
    ("Интерфейс Streamlit", "Streamlit interface"),
    ("Показатели и графики", "Metrics and charts"),
    ("Вопросы и отчёты в UI", "Questions and reports in the UI"),
    ("Доступ по токенам", "Access tokens"),
    ("Ограничения и атаки", "Limits and attacks"),
    ("Evals агента", "Agent evals"),
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
STAGE_05_SECTIONS = range(27, 30)
STAGE_06_SECTIONS = range(30, 33)
STAGE_07_SECTIONS = range(33, 37)
STAGE_08_SECTIONS = range(37, 40)
STAGE_09_SECTIONS = range(40, 43)


def number_of(ru_title: str) -> int:
    """Номер раздела по русскому заголовку: ссылки не ломаются при вставке разделов."""
    for index, (ru, _) in enumerate(CONTENTS):
        if ru == ru_title:
            return index + 1
    raise ValueError(f"Нет раздела {ru_title!r}")


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
