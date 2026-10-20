"""Язык PDF-гайда: каждый текст задаётся парой «русский — английский».

Язык выбирается один раз перед сборкой (set_language). Схемы рисуются
во время сборки документа, поэтому tr() внутри них тоже видит этот язык.
"""

LANGUAGES = ("ru", "en")
_current = {"lang": "ru"}


def set_language(lang: str) -> None:
    """Выбрать язык сборки: ru или en."""
    if lang not in LANGUAGES:
        raise ValueError(f"Неизвестный язык: {lang}")
    _current["lang"] = lang


def language() -> str:
    """Текущий язык сборки."""
    return _current["lang"]


def tr(ru: str, en: str) -> str:
    """Вернуть текст на текущем языке."""
    return ru if _current["lang"] == "ru" else en


def loc(value: str | dict[str, str]) -> str:
    """Значение из verification.json: общая строка или пара {"ru": ..., "en": ...}."""
    if isinstance(value, str):
        return value
    return value[_current["lang"]]
