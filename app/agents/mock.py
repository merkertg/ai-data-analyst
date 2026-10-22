"""A deterministic demo provider: real tools and checks, no language model.

It plans like a careful analyst would for "why did revenue change in <month>":
coverage → comparison, categories, regions, refunds → anomalies and stock of
the main category → report. The question is read only for a month, a year and
its language; every number in the report comes from real tool results and
passes the same evidence check as a model's report.
"""

import json
import re
from datetime import date
from typing import Any

from app.agents.contracts import AgentTurn, ProviderName, ToolCall
from app.agents.schemas import AnalysisReport, Evidence, Fact, Hypothesis

MOCK_MODEL = "mock-analyst-v1"

_MONTHS_RU = [
    "январ", "феврал", "март", "апрел", r"ма[йяе]", "июн",
    "июл", "август", "сентябр", "октябр", "ноябр", "декабр",
]  # fmt: skip
# English names and usual abbreviations, matched as whole words only: a prefix
# match once read the "dec" of "decline" as December (found by Stage 09 evals).
_MONTHS_EN = [
    "january|jan", "february|feb", "march|mar", "april|apr", "May",
    "june|jun", "july|jul", "august|aug", "september|sept|sep",
    "october|oct", "november|nov", "december|dec",
]  # fmt: skip
_NAMES = {
    "ru": [
        "январь", "февраль", "март", "апрель", "май", "июнь", "июль",
        "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
    ],
    "en": [
        "January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December",
    ],
}  # fmt: skip


def _language(question: str) -> str:
    """Russian if the question contains Cyrillic letters."""
    return "ru" if re.search("[а-яё]", question.lower()) else "en"


def _month_in(question: str) -> int | None:
    """The first month named in the question, 1-12."""
    text = question.lower()
    positions = []
    for index, stem in enumerate(_MONTHS_RU):
        if match := re.search(rf"\b{stem}", text):
            positions.append((match.start(), index + 1))
    for index, names in enumerate(_MONTHS_EN):
        # "May" is also a verb, so only the capitalised month name counts.
        source = question if names == "May" else text
        if match := re.search(rf"\b(?:{names})\.?(?![a-z])", source):
            positions.append((match.start(), index + 1))
    return min(positions)[1] if positions else None


def _shift(year: int, month: int, delta: int) -> tuple[int, int]:
    """Move a calendar month forwards or backwards."""
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1


def _month_period(year: int, month: int) -> dict[str, str]:
    """A calendar month as half-open start and end dates."""
    next_year, next_month = _shift(year, month, 1)
    return {
        "start": date(year, month, 1).isoformat(),
        "end": date(next_year, next_month, 1).isoformat(),
    }


def _call(call_id: str, name: str, arguments: dict[str, Any]) -> ToolCall:
    """The same shape of call a real model returns: arguments as JSON text."""
    return ToolCall(call_id, name, json.dumps(arguments))


def _items(calls: list[ToolCall]) -> list[dict[str, Any]]:
    """Function call items for the transcript, as in the Responses API."""
    return [
        {
            "type": "function_call",
            "call_id": call.call_id,
            "name": call.name,
            "arguments": call.arguments,
        }
        for call in calls
    ]


def _results(history: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Tool results already in the transcript, by call_id."""
    return {
        item["call_id"]: json.loads(item["output"])
        for item in history
        if item.get("type") == "function_call_output"
    }


def _question(history: list[dict[str, Any]]) -> str:
    """The original question from the first user message."""
    return str(json.loads(history[0]["content"])["question"])


class _Writer:
    """Collect facts and hypotheses whose evidence points at real values."""

    def __init__(self, results: dict[str, dict[str, Any]], language: str) -> None:
        self.results = results
        self.ru = language == "ru"

    def value(self, call_id: str, path: str) -> Any:
        """A value from a successful result, or None."""
        node: Any = self.results.get(call_id, {}).get("data")
        for part in path.split("."):
            if isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            elif isinstance(node, dict):
                node = node.get(part)
            else:
                return None
        return node

    def evidence(self, call_id: str, *paths: str) -> list[Evidence]:
        """Evidence for the listed paths that hold a value."""
        return [
            Evidence(call_id=call_id, field=path, value=str(value))
            for path in paths
            if (value := self.value(call_id, path)) is not None
        ]

    def text(self, ru: str, en: str) -> str:
        """The sentence in the question's language."""
        return ru if self.ru else en

    def falling(self) -> bool:
        """Did net revenue fall? Sorting by delta puts the biggest fall first."""
        net = self.value("mock-compare", "changes.net_revenue.absolute")
        return isinstance(net, str) and net.startswith("-")

    def main_group(self, call_id: str) -> int | None:
        """Index of the group that moved most in the direction of the total."""
        groups = self.value(call_id, "contributions")
        if not isinstance(groups, list) or not groups:
            return None
        return 0 if self.falling() else len(groups) - 1


class MockProvider:
    """Four scripted turns over real tool results; no network, no key."""

    provider: ProviderName = "mock"
    model = MOCK_MODEL

    def next_turn(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        remaining_seconds: float,
    ) -> AgentTurn:
        """Decide the next step from the results gathered so far."""
        results = _results(history)
        if "mock-coverage" not in results:
            return self._calls([_call("mock-coverage", "get_data_coverage", {})])
        question = _question(history)
        coverage = results["mock-coverage"].get("data", {})
        last = coverage.get("last_paid_on")
        if last is None:
            return self._final(self._no_data(_language(question)))
        target = self._target(question, date.fromisoformat(last))
        current = _month_period(*target)
        previous = _month_period(*_shift(*target, -1))
        comparison = {
            **current,
            "compare_start": previous["start"],
            "compare_end": previous["end"],
        }
        if "mock-compare" not in results:
            return self._calls(
                [
                    _call("mock-compare", "compare_periods", comparison),
                    _call("mock-category", "get_sales_by_category", comparison),
                    _call("mock-region", "get_sales_by_region", comparison),
                    _call("mock-refunds", "get_refund_statistics", current),
                ]
            )
        writer = _Writer(results, _language(question))
        main = writer.main_group("mock-category")
        category = (
            None
            if main is None
            else writer.value("mock-category", f"contributions.{main}.name")
        )
        if "mock-anomalies" not in results and category is not None:
            year_start = {"start": date(target[0], 1, 1).isoformat()}
            return self._calls(
                [
                    _call(
                        "mock-anomalies",
                        "detect_anomalies",
                        {
                            **year_start,
                            "end": current["end"],
                            "category": category,
                            "limit": 5,
                        },
                    ),
                    _call(
                        "mock-stock",
                        "get_inventory_history",
                        {**current, "category": category, "limit": 3},
                    ),
                ]
            )
        return self._final(self._report(writer, target))

    def _target(self, question: str, last_paid: date) -> tuple[int, int]:
        """The month asked about, or the last complete month with data."""
        month = _month_in(question)
        year_match = re.search(r"\b(20\d{2})\b", question)
        year = int(year_match.group(1)) if year_match else last_paid.year
        if month is None:
            following = date(*_shift(last_paid.year, last_paid.month, 1), 1)
            complete = (following - last_paid).days == 1
            return (
                (last_paid.year, last_paid.month)
                if complete
                else _shift(last_paid.year, last_paid.month, -1)
            )
        if year_match is None and (year, month) > (last_paid.year, last_paid.month):
            year -= 1
        return year, month

    def _calls(self, calls: list[ToolCall]) -> AgentTurn:
        """A turn that requests tools."""
        return AgentTurn(_items(calls), calls, None, self.model)

    def _final(self, report: AnalysisReport) -> AgentTurn:
        """A turn with the final report as a message item."""
        message = {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": report.model_dump_json()}],
        }
        return AgentTurn([message], [], report, self.model)

    def _no_data(self, language: str) -> AnalysisReport:
        """An honest report for an empty database."""
        ru = language == "ru"
        return AnalysisReport(
            language="ru" if ru else "en",
            summary="В базе нет оплаченных заказов: анализировать нечего."
            if ru
            else "The database has no paid orders, so there is nothing to analyse.",
            facts=[],
            hypotheses=[],
            recommendations=[],
            limitations=[_demo_note(ru)],
        )

    def _report(self, w: _Writer, target: tuple[int, int]) -> AnalysisReport:
        """Facts, hypotheses and recommendations from the gathered results."""
        language = "ru" if w.ru else "en"
        month = f"{_NAMES[language][target[1] - 1]} {target[0]}"
        before = _shift(*target, -1)
        previous = f"{_NAMES[language][before[1] - 1]} {before[0]}"
        net = w.value("mock-compare", "changes.net_revenue.absolute")
        percent = w.value("mock-compare", "changes.net_revenue.percent")
        current_net = w.value("mock-compare", "current.net_revenue")
        share = f" ({percent}%)" if percent is not None else ""
        facts = [
            Fact(
                statement=w.text(
                    f"Чистая выручка за {month}: {current_net}; изменение к "
                    f"предыдущему месяцу ({previous}): {net}{share}.",
                    f"Net revenue for {month} was {current_net}; the change "
                    f"against {previous} was {net}{share}.",
                ),
                evidence=w.evidence(
                    "mock-compare",
                    "current.net_revenue",
                    "changes.net_revenue.absolute",
                    "changes.net_revenue.percent",
                ),
            )
        ]
        hypotheses: list[Hypothesis] = []
        recommendations: list[str] = []
        for call_id, ru_kind, en_kind in (
            ("mock-category", "категорий", "categories"),
            ("mock-region", "регионов", "regions"),
        ):
            index = w.main_group(call_id)
            if index is None:
                continue
            group = f"contributions.{index}"
            name = w.value(call_id, f"{group}.name")
            delta = w.value(call_id, f"{group}.delta")
            part = w.value(call_id, f"{group}.contribution_percent")
            part_text = (
                w.text(f", {part}% общего изменения", f", {part}% of the total change")
                if part is not None
                else ""
            )
            facts.append(
                Fact(
                    statement=w.text(
                        f"Среди {ru_kind} сильнее всего "
                        f"{'снизилась' if w.falling() else 'выросла'} выручка "
                        f"{name}: {delta}{part_text}.",
                        f"Among {en_kind}, {name} "
                        f"{'fell' if w.falling() else 'grew'} the most: "
                        f"{delta}{part_text}.",
                    ),
                    evidence=w.evidence(
                        call_id,
                        f"{group}.name",
                        f"{group}.delta",
                        f"{group}.contribution_percent",
                    ),
                )
            )
        refund_category = w.value("mock-refunds", "categories.0.category")
        if refund_category is not None:
            refunds = w.value("mock-refunds", "categories.0.refunds")
            rate = w.value("mock-refunds", "categories.0.refund_rate_percent")
            rate_text = (
                w.text(
                    f" ({rate}% от продаж месяца)", f" ({rate}% of the month's sales)"
                )
                if rate is not None
                else ""
            )
            facts.append(
                Fact(
                    statement=w.text(
                        f"Больше всего возвратов за {month} — {refund_category}: "
                        f"{refunds}{rate_text}.",
                        f"The largest refunds in {month} were in {refund_category}: "
                        f"{refunds}{rate_text}.",
                    ),
                    evidence=w.evidence(
                        "mock-refunds",
                        "categories.0.category",
                        "categories.0.refunds",
                        "categories.0.refund_rate_percent",
                    ),
                )
            )
        main = w.main_group("mock-category")
        category = (
            None
            if main is None
            else w.value("mock-category", f"contributions.{main}.name")
        )
        zero_days = w.value("mock-stock", "products.0.zero_stock_days")
        if isinstance(zero_days, int) and zero_days > 0:
            product = w.value("mock-stock", "products.0.name")
            hypotheses.append(
                Hypothesis(
                    statement=w.text(
                        f"Товар {product} был без остатка {zero_days} дн. за "
                        f"{month}: дефицит мог ограничить продажи категории "
                        f"{category}.",
                        f"{product} had zero stock on {zero_days} days in {month}; "
                        f"the shortage may have limited {category} sales.",
                    ),
                    evidence=w.evidence(
                        "mock-stock", "products.0.name", "products.0.zero_stock_days"
                    ),
                )
            )
            recommendations.append(
                w.text(
                    f"Проверить поставки и складские остатки категории {category}.",
                    f"Check deliveries and stock levels of {category}.",
                )
            )
        candidates = w.value("mock-anomalies", "candidates_matching")
        if isinstance(candidates, int) and candidates > 0:
            hypotheses.append(
                Hypothesis(
                    statement=w.text(
                        f"Детектор аномалий вернул {candidates} кандидатов для "
                        f"категории {category} с начала года: это повод проверить "
                        "исходные строки, а не доказанная причина.",
                        f"The anomaly detector returned {candidates} candidates for "
                        f"{category} since the start of the year: rows to inspect, "
                        "not a proven cause.",
                    ),
                    evidence=w.evidence(
                        "mock-anomalies", "category", "candidates_matching"
                    ),
                )
            )
            recommendations.append(
                w.text(
                    "Разобрать кандидатов аномалий по исходным заказам и возвратам.",
                    "Review the anomaly candidates against the underlying orders "
                    "and refunds.",
                )
            )
        summary = w.text(
            f"За {month} чистая выручка изменилась на {net}{share} по сравнению "
            f"с предыдущим месяцем ({previous}).",
            f"In {month} net revenue changed by {net}{share} against {previous}.",
        )
        if category is not None:
            summary += w.text(
                f" Главный вклад в изменение — категория {category}.",
                f" The main contributor is the {category} category.",
            )
        return AnalysisReport(
            language=language,
            summary=summary,
            facts=facts,
            hypotheses=hypotheses,
            recommendations=recommendations,
            limitations=[
                _demo_note(w.ru),
                w.text(
                    "Гипотезы не доказывают причину: их нужно проверить по "
                    "исходным данным.",
                    "Hypotheses do not prove a cause; check them against the "
                    "source data.",
                ),
            ],
        )


def _demo_note(ru: bool) -> str:
    """Make the demo mode visible in every mock report."""
    return (
        "Демонстрационный режим: вопрос разобран по ключевым словам, "
        "языковая модель не вызывалась."
        if ru
        else "Demo mode: the question was parsed by keywords; no language model "
        "was called."
    )
