"""Check that a report only states numbers the tools actually returned.

Two rules, applied before a report is accepted:

1. Every evidence item points at a successful tool call of this run, and the
   value at its field path equals the quoted value exactly.
2. Every number written in a fact, hypothesis, recommendation or the summary
   equals one of the verified evidence values (the sign may be dropped:
   "fell by 291500.00" quotes "-291500.00"). Years, ISO dates and digits
   inside cited names ("Demo pumps 01") are not figures.

The model can still phrase things badly, but it cannot invent a figure.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agents.contracts import ToolTrace
from app.agents.schemas import AnalysisReport, Evidence

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# A number not glued to a letter, digit or hyphen (so "A01", "DN50" and
# "ЦН-100" are names, not figures). Thousands may be grouped with spaces.
_NUMBER = re.compile(
    r"(?<![\w.,\-−–])[-−–]?"
    r"(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)"
    r"(?!\w)"
)
# Ordinary, no-break and narrow no-break spaces between digit groups.
_SPACES = str.maketrans("", "", " \u00a0\u202f")
MISSING = object()


def resolve(data: Any, path: str) -> Any:
    """Follow a dotted path such as "contributions.0.delta" into tool data."""
    node = data
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return MISSING
    return node


def as_text(value: Any) -> str | None:
    """A scalar as the model sees it in JSON; objects and lists are not values."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float | str):
        return str(value)
    return None


def _decimal(text: str) -> Decimal | None:
    """A finite number or None; "-1 000,5" and "1,000.5" are both 1000.5."""
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _candidates(token: str) -> set[Decimal]:
    """Every reasonable reading of a written number, without its sign."""
    text = token.translate(_SPACES).lstrip("-−–")
    readings = []
    if "," in text and "." in text:
        readings.append(text.replace(",", ""))
    elif "," in text:
        readings.append(text.replace(",", "."))
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", text):
            readings.append(text.replace(",", ""))
    else:
        readings.append(text)
    return {abs(number) for item in readings if (number := _decimal(item)) is not None}


def numbers_in(text: str) -> list[str]:
    """Numbers that need evidence: dates and 4-digit years are excluded."""
    found = []
    for match in _NUMBER.finditer(_DATE.sub(" ", text)):
        token = match.group()
        if re.fullmatch(r"(19|20|21)\d{2}", token):
            continue
        found.append(token)
    return found


@dataclass
class _Allowed:
    """What a text may quote: numeric values and names such as "Demo pumps 01"."""

    numbers: set[Decimal] = field(default_factory=set)
    names: set[str] = field(default_factory=set)

    def add(self, evidence: list[Evidence]) -> None:
        """Numbers by absolute value; any other value is a quotable name."""
        for item in evidence:
            number = _decimal(item.value.translate(_SPACES))
            if number is not None:
                self.numbers.add(abs(number))
            elif len(item.value) > 1:
                self.names.add(item.value)

    def unsupported(self, text: str) -> list[str]:
        """Written numbers that match none of the allowed values.

        Quoted names are removed first: the digits in a cited product name
        are part of the name, not a figure.
        """
        for name in sorted(self.names, key=len, reverse=True):
            text = text.replace(name, " ")
        return [
            token for token in numbers_in(text) if not _candidates(token) & self.numbers
        ]


def check_report(report: AnalysisReport, trace: list[ToolTrace]) -> list[str]:
    """All problems in a report; an empty list means it is verified."""
    results = {item.call_id: item.result for item in trace}
    problems: list[str] = []

    def check_evidence(owner: str, items: list[Evidence]) -> None:
        for item in items:
            result = results.get(item.call_id)
            if result is None:
                problems.append(f"{owner}: unknown call_id {item.call_id!r}")
                continue
            if result.get("ok") is not True:
                problems.append(f"{owner}: call {item.call_id!r} returned an error")
                continue
            actual = as_text(resolve(result["data"], item.field))
            if actual is None:
                problems.append(
                    f"{owner}: {item.call_id}.{item.field} is not a single value"
                )
            elif actual != item.value:
                problems.append(
                    f"{owner}: {item.call_id}.{item.field} is {actual!r}, "
                    f"not {item.value!r}"
                )

    everything = _Allowed()
    parts = [("facts", item) for item in report.facts] + [
        ("hypotheses", item) for item in report.hypotheses
    ]
    counters = {"facts": 0, "hypotheses": 0}
    for kind, part in parts:
        owner = f"{kind}[{counters[kind]}]"
        counters[kind] += 1
        if kind == "facts" and not part.evidence:
            problems.append(f"{owner}: a fact needs at least one evidence item")
        check_evidence(owner, part.evidence)
        own = _Allowed()
        own.add(part.evidence)
        everything.add(part.evidence)
        for token in own.unsupported(part.statement):
            problems.append(f"{owner}: number {token!r} is not in its evidence")
    for token in everything.unsupported(report.summary):
        problems.append(f"summary: number {token!r} is not in any evidence")
    for index, text in enumerate(report.recommendations):
        for token in everything.unsupported(text):
            problems.append(
                f"recommendations[{index}]: number {token!r} is not in any evidence"
            )
    return problems
