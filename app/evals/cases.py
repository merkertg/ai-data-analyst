"""Eval questions and what a correct answer must contain.

A case states the question, which tools are reasonable, which values a
correct answer must cite and, for the reference run, which calls answer it.
Expected values are never written in the file: the Pandas oracle computes
them from the bundle, so the cases stay valid for a regenerated dataset.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evals.oracle import Oracle, money, percent, share

CASES_FILE = Path(__file__).resolve().parents[2] / "evals" / "cases.json"

Kind = Literal[
    "metric",
    "comparison",
    "contribution",
    "refunds",
    "products",
    "stock",
    "no_data",
    "refusal",
    "injection",
]
Metric = Literal[
    "paid_sales",
    "refunds",
    "net_revenue",
    "paid_orders",
    "average_order_value",
    "change_absolute",
    "change_percent",
    "group_delta",
    "group_share",
    "largest_decline",
    "refund_rate",
    "category_refunds",
    "refund_count",
    "most_refunded_category",
    "top_product",
    "top_product_sales",
    "zero_stock_days",
    "last_stock_quantity",
    "zero_stock_leader",
    "max_line_quantity",
    "first_paid_on",
    "last_paid_on",
]
Period = tuple[date, date]


class _Strict(BaseModel):
    """Unknown keys in the cases file are mistakes, not silently ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Expectation(_Strict):
    """One value a correct answer must cite as evidence."""

    metric: Metric
    period: Period | None = None
    previous: Period | None = None
    of: (
        Literal[
            "net_revenue", "paid_sales", "refunds", "paid_orders", "average_order_value"
        ]
        | None
    ) = None
    dimension: Literal["category", "region"] | None = None
    name: str | None = None


class Cite(_Strict):
    """Where the reference run reads a value: a path, or a list item by key."""

    path: str | None = None
    list: str | None = None
    where: dict[str, str] | None = None
    field: str | None = None
    label: str = Field(min_length=1)

    @model_validator(mode="after")
    def one_form(self) -> "Cite":
        """Either a direct path or list + where + field."""
        direct = self.path is not None
        listed = None not in (self.list, self.where, self.field)
        if direct == listed:
            raise ValueError("cite needs either path or list, where and field")
        return self


class ReferenceCall(_Strict):
    """A tool call of the reference run and the values it cites."""

    tool: str
    arguments: dict[str, Any]
    cite: list[Cite] = Field(default_factory=list)


class EvalCase(_Strict):
    """One question with its scoring rules."""

    id: str = Field(pattern=r"^[A-Z]\d{2}$")
    kind: Kind
    language: Literal["ru", "en"]
    question: str = Field(min_length=3, max_length=2000)
    tools_any: list[str] = Field(default_factory=list)
    expect: list[Expectation] = Field(default_factory=list)
    no_facts: bool = False
    forbidden_numbers: list[str] = Field(default_factory=list)
    reference: list[ReferenceCall] = Field(default_factory=list)


def load_cases(path: Path = CASES_FILE) -> list[EvalCase]:
    """Read and validate the cases file; ids must be unique."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = [EvalCase.model_validate(item) for item in raw["cases"]]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("eval case ids must be unique")
    return cases


def _period(value: Period | None) -> Period:
    """A required period; the cases file is validated by tests."""
    if value is None:
        raise ValueError("this metric needs a period")
    return value


def expected_values(expectation: Expectation, oracle: Oracle) -> set[str]:
    """The acceptable cited values: numbers as plain decimal text, or names."""
    metric = expectation.metric
    if metric == "first_paid_on":
        return {oracle.coverage()[0].isoformat()}
    if metric == "last_paid_on":
        return {oracle.coverage()[1].isoformat()}
    period = _period(expectation.period)
    if metric in {
        "paid_sales",
        "refunds",
        "net_revenue",
        "paid_orders",
        "average_order_value",
    }:
        return {_metric_text(oracle, metric, period)}
    if metric in {"change_absolute", "change_percent"}:
        previous = _period(expectation.previous)
        of = expectation.of or "net_revenue"
        current_value = _metric_number(oracle, of, period)
        previous_value = _metric_number(oracle, of, previous)
        if metric == "change_absolute":
            change = current_value - previous_value
            return {str(change if of == "paid_orders" else money(change))}
        return {str(percent(current_value - previous_value, previous_value))}
    if metric in {"group_delta", "group_share", "largest_decline"}:
        previous = _period(expectation.previous)
        column = expectation.dimension or "category"
        deltas = oracle.group_deltas(column, period, previous)
        if metric == "largest_decline":
            return {min(sorted(deltas), key=lambda name: deltas[name])}
        delta = deltas[expectation.name or ""]
        if metric == "group_delta":
            return {str(money(delta))}
        return {str(share(delta, sum(deltas.values())))}
    if metric in {"refund_rate", "category_refunds", "refund_count"}:
        amount, count = oracle.refunds_of(expectation.name or "", period)
        if metric == "category_refunds":
            return {str(money(amount))}
        if metric == "refund_count":
            return {str(count)}
        sales = oracle.totals(period, "category", expectation.name).sales
        return {str(percent(amount, sales))}
    if metric == "most_refunded_category":
        names = set(oracle.refunds["category"])
        return {max(sorted(names), key=lambda name: oracle.refunds_of(name, period)[0])}
    if metric in {"top_product", "top_product_sales"}:
        best = oracle.products_by_sales(period, expectation.name).iloc[0]
        if metric == "top_product_sales":
            return {str(money(int(best["amount"])))}
        return {str(best["sku"]), str(best["name"])}
    if metric in {"zero_stock_days", "last_stock_quantity"}:
        rows = oracle.stock_of(expectation.name or "", period)
        if metric == "zero_stock_days":
            return {str(int((rows["quantity"] == 0).sum()))}
        return {str(int(rows.iloc[-1]["quantity"]))}
    if metric == "zero_stock_leader":
        return set(oracle.zero_stock_leader(expectation.name or "", period))
    return {str(oracle.max_line_quantity(expectation.name or "", period))}


def _metric_number(oracle: Oracle, metric: str, period: Period) -> int:
    """A metric as an integer: kopecks for money, a count for orders."""
    totals = oracle.totals(period)
    if metric == "paid_orders":
        return totals.orders
    if metric == "average_order_value":
        # Half-up rounding of sales / orders to whole kopecks.
        return (2 * totals.sales + totals.orders) // (2 * totals.orders)
    return {"paid_sales": totals.sales, "refunds": totals.refunds}.get(
        metric, totals.net
    )


def _metric_text(oracle: Oracle, metric: str, period: Period) -> str:
    """The metric as the API writes it."""
    number = _metric_number(oracle, metric, period)
    return str(number) if metric == "paid_orders" else str(money(number))


def same_value(cited: str, expected: str) -> bool:
    """Numbers compare by value ("0" equals "0.00"); other text exactly."""
    try:
        return Decimal(cited) == Decimal(expected)
    except ArithmeticError:
        return cited == expected
