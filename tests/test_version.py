"""Версия проекта записана в двух местах; тест не даёт им разойтись."""

import tomllib
from pathlib import Path

from app import __version__

# Путь строим от файла теста, а не от текущей папки терминала.
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    """app.__version__ совпадает с полем version в pyproject.toml."""
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]

    assert __version__ == project["version"]
