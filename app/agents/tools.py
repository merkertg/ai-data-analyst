"""The only operations the model may request: fixed, read-only analytics tools.

The model sends a tool name and JSON arguments. Neither ever becomes Python
code or SQL: the name selects a function from a fixed registry, the arguments
are validated by a strict Pydantic model, and the function runs the same
parameterised queries as the REST API. Results are JSON with money as strings.
"""

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.schemas import strict_schema
from app.analytics.details import (
    data_coverage,
    refunds_by_category,
    stock_history,
    top_products,
)
from app.analytics.models import Dimension, Period
from app.analytics.service import compare_periods as compare_core
from app.db.session import DatabaseNotConfigured
from app.llm.errors import ToolDataUnavailable
from app.schemas.analytics import (
    AnomalyQuery,
    ChangeOut,
    ComparisonQuery,
    MetricsOut,
    OptionalComparisonQuery,
    calendar_months,
)
from app.services import analytics

# Tighter than the REST API (120 months): a tool result must fit the context.
AGENT_MAX_MONTHS = 24
MAX_ARGUMENT_CHARACTERS = 2_000
MAX_RESULT_CHARACTERS = 16_000
ANOMALY_SEED = 42

SessionFactory = Callable[[], AbstractContextManager[Session]]


class _Arguments(BaseModel):
    """Reject unknown fields and implicit type coercion ("5" is not 5)."""

    model_config = ConfigDict(extra="forbid", strict=True)


class NoArguments(_Arguments):
    """The tool takes no arguments."""


class PeriodArguments(_Arguments):
    """A half-open Moscow period [start, end) of at most 24 calendar months."""

    start: date = Field(description="Inclusive first date, YYYY-MM-DD, Moscow time")
    end: date = Field(
        description="Exclusive end date, YYYY-MM-DD; Sep 2026 ends 2026-10-01"
    )

    @model_validator(mode="after")
    def check_period(self) -> Self:
        """Same rules as the API, with the smaller agent month limit."""
        _check(self.start, self.end, "period")
        return self

    def period(self) -> Period:
        """The validated interval as the core type."""
        return Period(self.start, self.end)


class ComparisonArguments(PeriodArguments):
    """The analysed period and the period it is compared with."""

    compare_start: date = Field(description="Comparison period start, inclusive")
    compare_end: date = Field(description="Comparison period end, exclusive")

    @model_validator(mode="after")
    def check_comparison(self) -> Self:
        """The comparison period follows the same rules."""
        _check(self.compare_start, self.compare_end, "comparison")
        return self


class ListArguments(PeriodArguments):
    """A period, an optional category filter and a result limit."""

    category: str | None = Field(
        max_length=100, description="Exact category name, or null for all"
    )
    limit: int = Field(ge=1, le=20, description="Maximum number of rows, 1-20")


def _check(start: date, end: date, label: str) -> None:
    """Reject empty, reversed or too long intervals before any SQL."""
    if start >= end:
        raise ValueError(f"{label}: start must be earlier than the exclusive end")
    if calendar_months(start, end) > AGENT_MAX_MONTHS:
        raise ValueError(f"{label}: at most {AGENT_MAX_MONTHS} months are allowed")


def _json(value: Any) -> Any:
    """Dataclasses, dates and Decimal to JSON-ready values; money stays text."""
    return TypeAdapter(type(value)).dump_python(value, mode="json")


def get_data_coverage(session: Session, _: NoArguments) -> dict[str, Any]:
    """Dates that contain data and the exact category and region names."""
    return {
        "timezone": "Europe/Moscow",
        **_json(data_coverage(session)),
    }


def get_revenue(session: Session, arguments: PeriodArguments) -> dict[str, Any]:
    """Revenue totals of a period with calendar month buckets."""
    query = OptionalComparisonQuery(start=arguments.start, end=arguments.end)
    return analytics.revenue(session, query).model_dump(mode="json")


def compare_periods(session: Session, arguments: ComparisonArguments) -> dict[str, Any]:
    """Every metric of two periods and its exact change."""
    changes = compare_core(
        session,
        arguments.period(),
        Period(arguments.compare_start, arguments.compare_end),
    )
    aov = changes.average_order_value
    return {
        "currency": "RUB",
        "current": MetricsOut.model_validate(changes.current).model_dump(mode="json"),
        "previous": MetricsOut.model_validate(changes.previous).model_dump(mode="json"),
        "changes": {
            name: ChangeOut.model_validate(getattr(changes, name)).model_dump(
                mode="json"
            )
            for name in ("paid_sales", "refunds", "net_revenue", "paid_orders")
        }
        | {
            "average_order_value": None
            if aov is None
            else ChangeOut.model_validate(aov).model_dump(mode="json")
        },
    }


def _contributions(
    session: Session, arguments: ComparisonArguments, dimension: Dimension
) -> dict[str, Any]:
    """Net revenue change of both periods split by category or region."""
    query = ComparisonQuery(
        start=arguments.start,
        end=arguments.end,
        compare_start=arguments.compare_start,
        compare_end=arguments.compare_end,
    )
    return analytics.group_contributions(session, query, dimension).model_dump(
        mode="json"
    )


def get_sales_by_category(
    session: Session, arguments: ComparisonArguments
) -> dict[str, Any]:
    """Each category's net revenue change and share of the total change."""
    return _contributions(session, arguments, "category")


def get_sales_by_region(
    session: Session, arguments: ComparisonArguments
) -> dict[str, Any]:
    """Each customer region's net revenue change and share of the total change."""
    return _contributions(session, arguments, "region")


def get_top_products(session: Session, arguments: ListArguments) -> dict[str, Any]:
    """Products with the largest paid sales in a period."""
    rows = top_products(
        session, arguments.period(), arguments.limit, arguments.category
    )
    return {
        "currency": "RUB",
        "period": _json(arguments.period()),
        "category": arguments.category,
        "products": [_json(row) for row in rows],
    }


def get_refund_statistics(
    session: Session, arguments: PeriodArguments
) -> dict[str, Any]:
    """Refunds processed in a period per category and their rate to sales."""
    return {
        "currency": "RUB",
        "period": _json(arguments.period()),
        "rate_definition": "refunds processed in the period / sales paid in it",
        "categories": [
            _json(row) for row in refunds_by_category(session, arguments.period())
        ],
    }


def get_inventory_history(session: Session, arguments: ListArguments) -> dict[str, Any]:
    """Zero-stock days per product; missing snapshots are not counted as zero."""
    rows = stock_history(
        session, arguments.period(), arguments.limit, arguments.category
    )
    return {
        "period": _json(arguments.period()),
        "category": arguments.category,
        "products": [_json(row) for row in rows],
    }


def detect_anomalies(session: Session, arguments: ListArguments) -> dict[str, Any]:
    """Stage 05 candidates; rule-based findings come before Isolation Forest."""
    query = AnomalyQuery(start=arguments.start, end=arguments.end, seed=ANOMALY_SEED)
    report = analytics.anomalies(session, query).model_dump(mode="json")
    findings = [
        finding
        for finding in report["findings"]
        if arguments.category is None
        or finding["entity"].get("category") == arguments.category
    ]
    # Stable sort: explainable rules first, the exploratory forest last.
    findings.sort(key=lambda item: item["method"] == "isolation_forest")
    methods: dict[str, int] = {}
    for finding in findings:
        methods[finding["method"]] = methods.get(finding["method"], 0) + 1
    return {
        "period": report["period"],
        "seed": report["seed"],
        "category": arguments.category,
        "candidates_total": report["finding_count"],
        "candidates_matching": len(findings),
        "methods": methods,
        "findings": findings[: arguments.limit],
        "note": "Candidates to investigate, not proven causes.",
    }


@dataclass(frozen=True)
class Tool:
    """A registry entry: description, argument model and implementation."""

    description: str
    arguments: type[_Arguments]
    run: Callable[[Session, Any], dict[str, Any]]


TOOLS: dict[str, Tool] = {
    "get_data_coverage": Tool(
        "First and last dates with sales, refunds and stock, plus the exact "
        "category and region names. Call it first to map the question to dates.",
        NoArguments,
        get_data_coverage,
    ),
    "get_revenue": Tool(
        "Paid sales, processed refunds and net revenue of a period, with "
        "calendar month buckets.",
        PeriodArguments,
        get_revenue,
    ),
    "compare_periods": Tool(
        "Compare two periods: paid sales, refunds, net revenue, paid orders and "
        "average order value with exact and percentage changes.",
        ComparisonArguments,
        compare_periods,
    ),
    "get_sales_by_category": Tool(
        "Split the net revenue change between two periods by product category; "
        "contribution_percent is each category's share of the total change.",
        ComparisonArguments,
        get_sales_by_category,
    ),
    "get_sales_by_region": Tool(
        "Split the net revenue change between two periods by customer region.",
        ComparisonArguments,
        get_sales_by_region,
    ),
    "get_top_products": Tool(
        "Products with the largest paid sales in a period, optionally within "
        "one category.",
        ListArguments,
        get_top_products,
    ),
    "get_refund_statistics": Tool(
        "Refund count, amount and refund rate per category for a period.",
        PeriodArguments,
        get_refund_statistics,
    ),
    "detect_anomalies": Tool(
        "Statistical and Isolation Forest anomaly candidates in a period, "
        "optionally for one category. Candidates are not proven causes.",
        ListArguments,
        detect_anomalies,
    ),
    "get_inventory_history": Tool(
        "Zero-stock days and stock levels per product in a period, optionally "
        "for one category.",
        ListArguments,
        get_inventory_history,
    ),
}


def _parameters(model: type[_Arguments]) -> dict[str, Any]:
    """Strict-mode parameters: every property required, nothing extra."""
    schema = strict_schema(model)
    schema.setdefault("properties", {})
    schema["required"] = list(schema["properties"])
    return schema


# Function tools in the Responses API format. strict: the model's arguments
# must match the schema; the server still validates them again below.
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": name,
        "description": tool.description,
        "parameters": _parameters(tool.arguments),
        "strict": True,
    }
    for name, tool in TOOLS.items()
]


def tool_error(code: str, message: str) -> dict[str, Any]:
    """A predictable error for the model, without exceptions or SQL."""
    return {"ok": False, "error": {"code": code, "message": message}}


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject {"limit": 1, "limit": 20}: duplicate keys make JSON ambiguous."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _validation_message(error: ValidationError) -> str:
    """Field and reason for the model; the rejected input is not echoed."""
    parts = []
    for item in error.errors(include_input=False, include_url=False)[:5]:
        location = ".".join(str(part) for part in item["loc"]) or "arguments"
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts)


class ToolExecutor:
    """Run one validated tool call in its own read-only session."""

    def __init__(self, sessions: SessionFactory) -> None:
        """sessions opens a REPEATABLE READ READ ONLY session per call."""
        self.sessions = sessions

    def __call__(
        self, name: str, arguments: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return validated arguments and a JSON result, or a tool error.

        A tool error goes back to the model, which can correct its call. A
        database failure stops the whole run: the data cannot be trusted.
        """
        tool = TOOLS.get(name)
        if tool is None:
            return {}, tool_error("unknown_tool", f"Allowed tools: {', '.join(TOOLS)}")
        if len(arguments) > MAX_ARGUMENT_CHARACTERS:
            return {}, tool_error("invalid_arguments", "Arguments are too long.")
        try:
            json.loads(arguments, object_pairs_hook=_unique_keys)
            parsed = tool.arguments.model_validate_json(arguments)
        except ValidationError as error:
            return {}, tool_error("invalid_arguments", _validation_message(error))
        except ValueError:
            return {}, tool_error(
                "invalid_arguments", "Arguments must be one JSON object."
            )
        safe_arguments = parsed.model_dump(mode="json")
        try:
            with self.sessions() as session:
                data = tool.run(session, parsed)
        except (DatabaseNotConfigured, SQLAlchemyError):
            raise ToolDataUnavailable() from None
        result = {"ok": True, "data": data}
        if len(json.dumps(result, ensure_ascii=False)) > MAX_RESULT_CHARACTERS:
            return safe_arguments, tool_error(
                "result_too_large", "Use a shorter period, a category or a lower limit."
            )
        return safe_arguments, result
