"""Tool definitions and argument checks, without a database.

The session factory fails the test if it is ever opened: every rejected call
below must stop before SQL.
"""

from contextlib import AbstractContextManager
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.agents.schemas import AnalysisReport, strict_schema
from app.agents.tools import TOOL_DEFINITIONS, TOOLS, ToolExecutor

SEPTEMBER = '{"start": "2026-09-01", "end": "2026-10-01"}'


def no_sessions() -> AbstractContextManager[Session]:
    """Any SQL in these tests is a failure."""
    raise AssertionError("arguments must be rejected before a session opens")


def objects(schema: Any) -> list[dict[str, Any]]:
    """Every object schema inside a JSON Schema document."""
    found = []
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            found.append(schema)
        for value in schema.values():
            found += objects(value)
    elif isinstance(schema, list):
        for value in schema:
            found += objects(value)
    return found


def test_registry_has_the_course_tools() -> None:
    """Nine read-only tools; build_chart arrives with the UI in Stage 08."""
    assert list(TOOLS) == [
        "get_data_coverage",
        "get_revenue",
        "compare_periods",
        "get_sales_by_category",
        "get_sales_by_region",
        "get_top_products",
        "get_refund_statistics",
        "detect_anomalies",
        "get_inventory_history",
    ]
    assert [tool["name"] for tool in TOOL_DEFINITIONS] == list(TOOLS)


@pytest.mark.parametrize(
    "schema",
    [tool["parameters"] for tool in TOOL_DEFINITIONS] + [strict_schema(AnalysisReport)],
    ids=[tool["name"] for tool in TOOL_DEFINITIONS] + ["analysis_report"],
)
def test_schemas_follow_strict_mode(schema: dict[str, Any]) -> None:
    """Every object lists all properties as required and allows nothing else."""
    for node in objects(schema):
        assert node.get("additionalProperties") is False
        assert sorted(node.get("required", [])) == sorted(node.get("properties", {}))
    text = str(schema)
    for keyword in ("minLength", "maxLength", "'title'", "'default'"):
        assert keyword not in text


def test_tool_definitions_are_strict_functions() -> None:
    """The Responses API function format with strict argument checking."""
    for tool in TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        assert tool["strict"] is True
        assert tool["description"]


@pytest.mark.parametrize(
    ("name", "arguments", "code"),
    [
        ("drop_table", "{}", "unknown_tool"),
        ("get_revenue", "not json", "invalid_arguments"),
        ("get_revenue", "[]", "invalid_arguments"),
        (
            "get_revenue",
            '{"start": "2026-09-01", "start": "2026-08-01", "end": "2026-10-01"}',
            "invalid_arguments",
        ),
        (
            "get_revenue",
            '{"start": "2026-09-01", "end": "2026-10-01", "sql": "DROP TABLE"}',
            "invalid_arguments",
        ),
        (
            "get_revenue",
            '{"start": "2026-10-01", "end": "2026-09-01"}',
            "invalid_arguments",
        ),
        (
            "get_revenue",
            '{"start": "2024-01-01", "end": "2026-10-01"}',
            "invalid_arguments",
        ),
        (
            "get_revenue",
            '{"start": "2026-13-01", "end": "2026-10-01"}',
            "invalid_arguments",
        ),
        (
            "get_top_products",
            SEPTEMBER[:-1] + ', "category": null, "limit": "5"}',
            "invalid_arguments",
        ),
        (
            "get_top_products",
            SEPTEMBER[:-1] + ', "category": null, "limit": 50}',
            "invalid_arguments",
        ),
        (
            "compare_periods",
            '{"start": "2026-09-01", "end": "2026-10-01"}',
            "invalid_arguments",
        ),
        ("get_data_coverage", '{"x": 1}', "invalid_arguments"),
        ("get_revenue", '{"start": "' + "9" * 3000 + '"}', "invalid_arguments"),
    ],
    ids=[
        "unknown tool",
        "not json",
        "not an object",
        "duplicate key",
        "extra field",
        "reversed period",
        "over 24 months",
        "not a date",
        "limit as text",
        "limit too large",
        "missing comparison",
        "arguments for a no-argument tool",
        "too long",
    ],
)
def test_invalid_calls_return_errors_without_sql(
    name: str, arguments: str, code: str
) -> None:
    """The model gets a readable error and can correct its next call."""
    safe_arguments, result = ToolExecutor(no_sessions)(name, arguments)

    assert safe_arguments == {}
    assert result["ok"] is False
    assert result["error"]["code"] == code
    assert "DROP" not in result["error"]["message"]


def test_dates_are_accepted_as_iso_text() -> None:
    """Strict mode still reads JSON date strings; the period then runs SQL."""
    with pytest.raises(AssertionError, match="before a session opens"):
        ToolExecutor(no_sessions)(
            "get_revenue", '{"start": "2026-09-01", "end": "2026-10-01"}'
        )
