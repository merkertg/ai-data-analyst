"""The demo planner: language, month and target period from a question."""

from datetime import date

import pytest

from app.agents.mock import MockProvider, _language, _month_in


@pytest.mark.parametrize(
    ("question", "month"),
    [
        ("Почему в сентябре снизилась выручка?", 9),
        ("Выручка в мае и июне", 5),
        ("Сравни март с февралём", 3),
        ("What happened in July?", 7),
        ("Revenue for Sep vs Aug", 9),
        ("Почему упала выручка?", None),
        # Stage 09 evals: words that start like a month are not months.
        ("Which category drove the revenue decline in September 2026?", 9),
        ("How did market share change in October?", 10),
        ("Separate refunds from sales for Aug.", 8),
        ("What may explain the drop in June?", 6),
        ("Sales in May 2026", 5),
        ("Revenue in sept. 2026", 9),
    ],
)
def test_first_named_month_is_the_target(question: str, month: int | None) -> None:
    """Russian stems and English names or abbreviations are recognised."""
    assert _month_in(question) == month


def test_language_follows_the_question() -> None:
    """Cyrillic means a Russian report, otherwise English."""
    assert _language("Почему?") == "ru"
    assert _language("Why?") == "en"


@pytest.mark.parametrize(
    ("question", "target"),
    [
        ("Что было в июле?", (2026, 7)),
        ("Что было в декабре?", (2025, 12)),
        ("Что было в декабре 2026?", (2026, 12)),
        ("Почему упала выручка?", (2026, 9)),
    ],
    ids=["named month", "future month means last year", "explicit year", "no month"],
)
def test_target_month(question: str, target: tuple[int, int]) -> None:
    """Data ends on 2026-09-30: September is the last complete month."""
    assert MockProvider()._target(question, date(2026, 9, 30)) == target


def test_incomplete_last_month_is_skipped() -> None:
    """Data up to 2026-10-01 does not make October a complete month."""
    assert MockProvider()._target("Как дела?", date(2026, 10, 1)) == (2026, 9)
