"""Данные проекта для PDF: настоящий код, версии из uv.lock, схемы OpenAPI.

Всё, что можно прочитать из проекта, читается при сборке — PDF не расходится
с кодом. Выводы команд, которые требуют запущенной базы, записаны ниже
константами; те же числа проверяют интеграционные тесты.
"""

import ast
import json
import re
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read_source(relative: str) -> str:
    """Прочитать файл проекта, чтобы PDF показывал настоящий код."""
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _definition_source(relative: str, name: str, kind: type) -> str:
    """Исходник функции или класса вместе с декораторами по имени."""
    source = read_source(relative)
    for item in ast.walk(ast.parse(source)):
        if isinstance(item, kind) and getattr(item, "name", None) == name:
            decorators = getattr(item, "decorator_list", [])
            first = min([item.lineno] + [d.lineno for d in decorators])
            return "\n".join(source.splitlines()[first - 1 : item.end_lineno])
    raise ValueError(f"{name} не найден в {relative}")


def function_source(relative: str, name: str) -> str:
    """Исходник функции вместе с декораторами."""
    return _definition_source(relative, name, ast.FunctionDef)


def class_source(relative: str, name: str) -> str:
    """Исходник класса целиком."""
    return _definition_source(relative, name, ast.ClassDef)


def source_slice(relative: str, start: str, end: str) -> str:
    """Строки файла от первой, содержащей start, до строки, равной end.

    end сравнивается со строкой без отступов целиком: так ")" не совпадёт
    со скобкой внутри get_settings().
    """
    lines = read_source(relative).splitlines()
    first = next(i for i, line in enumerate(lines) if start in line)
    last = next(i for i in range(first, len(lines)) if lines[i].strip() == end)
    return "\n".join(lines[first : last + 1])


def without_comments(code: str) -> str:
    """Отрывок кода без строк-комментариев: короче и не зависит от языка."""
    return "\n".join(
        line for line in code.splitlines() if not line.strip().startswith("#")
    )


def locked_dependencies() -> tuple[list[tuple[str, str, str]], int]:
    """Прямые зависимости из pyproject.toml с версиями из uv.lock."""
    project = tomllib.loads(read_source("pyproject.toml"))
    lock = tomllib.loads(read_source("uv.lock"))
    versions = {item["name"]: item["version"] for item in lock["package"]}

    def name_of(spec: str) -> str:
        """Имя пакета без extras и ограничений версии."""
        return re.split(r"[\[<>=!~ ;]", spec, maxsplit=1)[0].lower()

    direct = [(name_of(spec), "runtime") for spec in project["project"]["dependencies"]]
    for spec in project["dependency-groups"]["dev"]:
        direct.append((name_of(spec), "dev"))
    rows = [(name, versions[name], group) for name, group in direct]
    # Две библиотеки, на которых стоит FastAPI: их версии тоже важно знать.
    rows += [(name, versions[name], "fastapi") for name in ("starlette", "pydantic")]
    return rows, len(lock["package"])


def app_facts() -> dict[str, str]:
    """Схема HealthResponse и пример JSON из настоящего приложения."""
    # Скрипт запускается как scripts/build_guide.py: корень добавляем явно.
    sys.path.insert(0, str(PROJECT_ROOT))
    from app.main import HealthResponse, app

    schema = app.openapi()["components"]["schemas"]["HealthResponse"]
    return {
        "schema": json.dumps(schema, ensure_ascii=False, indent=2),
        "model_json": HealthResponse(status="ok").model_dump_json(),
    }


def schema_counts() -> dict[str, int]:
    """Сколько таблиц, ограничений и индексов в схеме данных (без reports)."""
    sys.path.insert(0, str(PROJECT_ROOT))
    import app.db.models  # noqa: F401 — регистрирует таблицы
    from app.db.base import Base

    # Схема данных этапа 02; таблица reports этапа 06 описана отдельно.
    tables = [t for name, t in Base.metadata.tables.items() if name != "reports"]
    counts = {"tables": len(tables), "indexes": 0}
    for table in tables:
        counts["indexes"] += len(table.indexes)
        for constraint in table.constraints:
            kind = type(constraint).__name__
            counts[kind] = counts.get(kind, 0) + 1
    counts["constraints"] = sum(
        value for key, value in counts.items() if key.endswith("Constraint")
    )
    return counts


# ---------- Записанные результаты экспериментов этапа 01 ----------
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

# ---------- Записанные выводы этапа 02 (база разработки, psql) ----------
PSQL_ERRORS = """ERROR:  new row for relation "order_items" violates check constraint
        "ck_order_items_quantity_positive"
DETAIL:  Failing row contains (7, 1, 3, 0, 100.00, 0.0000).

ERROR:  update or delete on table "products" violates foreign key constraint
        "fk_inventory_snapshots_product_id_products" on table "inventory_snapshots"
DETAIL:  Key (id)=(1) is still referenced from table "inventory_snapshots"."""

PSQL_ORDER_TOTALS = """ order_id |        customer        |        paid_at         | items | order_total
----------+------------------------+------------------------+-------+-------------
        1 | ООО «ТехМонтаж-Север»  | 2026-09-05 09:00:00+00 |     2 |   190000.00
        2 | АО «Южный химкомбинат» | 2026-09-20 06:30:00+00 |     1 |   120000.00
        5 | ООО «ТехМонтаж-Север»  | 2026-09-30 22:30:00+00 |     1 |    18000.00"""

PSQL_NET_REVENUE = """   month    | paid_sales | refunds | net_revenue
------------+------------+---------+-------------
 2026-09-01 |  310000.00 | 1000.00 |   309000.00
 2026-10-01 |   18000.00 |  500.00 |    17500.00"""

PSQL_CATEGORIES = """     category      | paid_sales | share_percent
-------------------+------------+---------------
 Насосы            |  300000.00 |          91.5
 Запорная арматура |   18000.00 |           5.5
 Датчики           |   10000.00 |           3.0"""

PSQL_DOUBLE_COUNT = """ naive_sales | correct_sales | refunds
-------------+---------------+---------
   338000.00 |     328000.00 | 1500.00"""

ALEMBIC_OUTPUT = """$ uv run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Initial schema: ...
$ uv run alembic current
0001 (head)
$ uv run alembic check
No new upgrade operations detected."""

READY_OUTPUT = """# база работает / database running
HTTP/1.1 200 OK                   {"status":"ready","revision":"0001"}
# docker compose stop db
HTTP/1.1 503 Service Unavailable  {"detail":"Database is not ready"}
# docker compose start db
HTTP/1.1 200 OK                   {"status":"ready","revision":"0001"}"""
