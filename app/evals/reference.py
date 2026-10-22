"""A scripted provider that answers each case with its reference calls.

It is not a model: it calls exactly the tools written in the case and cites
the named fields. Its purpose is to check the eval pipeline itself. If the
reference run fails a case, either the case is not answerable with the
available tools or the SQL tools and the Pandas oracle disagree.
"""

import json
from typing import Any

from app.agents.contracts import AgentTurn, ProviderName, ToolCall
from app.agents.evidence import MISSING, as_text, resolve
from app.agents.schemas import AnalysisReport, Evidence, Fact
from app.evals.cases import Cite, EvalCase

REFERENCE_MODEL = "reference-v1"


def _cite(data: Any, cite: Cite) -> tuple[str, str] | None:
    """The field path and text value a cite points at, or None."""
    if cite.path is not None:
        path = cite.path
    else:
        rows = resolve(data, cite.list or "")
        if not isinstance(rows, list):
            return None
        index = next(
            (
                position
                for position, row in enumerate(rows)
                if all(
                    as_text(row.get(key)) == value
                    for key, value in (cite.where or {}).items()
                )
            ),
            None,
        )
        if index is None:
            return None
        path = f"{cite.list}.{index}.{cite.field}"
    value = resolve(data, path)
    text = None if value is MISSING else as_text(value)
    return None if text is None else (path, text)


class ReferenceProvider:
    """Two turns: the case's reference calls, then a report citing them."""

    provider: ProviderName = "mock"
    model = REFERENCE_MODEL

    def __init__(self, case: EvalCase) -> None:
        """Answer exactly this case."""
        self.case = case

    def next_turn(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        remaining_seconds: float,
    ) -> AgentTurn:
        """Call the reference tools first; then report what they returned."""
        results = {
            item["call_id"]: json.loads(item["output"])
            for item in history
            if item.get("type") == "function_call_output"
        }
        calls = [
            ToolCall(f"ref-{index}", call.tool, json.dumps(call.arguments))
            for index, call in enumerate(self.case.reference, start=1)
        ]
        if calls and calls[0].call_id not in results:
            items = [
                {
                    "type": "function_call",
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments": call.arguments,
                }
                for call in calls
            ]
            return AgentTurn(items, calls, None, self.model)
        facts = []
        for call, reference in zip(calls, self.case.reference, strict=True):
            data = results.get(call.call_id, {}).get("data")
            for cite in reference.cite:
                found = _cite(data, cite)
                if found is None:
                    continue
                path, value = found
                facts.append(
                    Fact(
                        statement=f"{cite.label}: {value}.",
                        evidence=[
                            Evidence(call_id=call.call_id, field=path, value=value)
                        ],
                    )
                )
        ru = self.case.language == "ru"
        if not self.case.reference:
            summary = (
                "Это вне возможностей аналитика: он только читает агрегированные "
                "данные о продажах."
                if ru
                else "This is outside the analyst's scope: it only reads "
                "aggregated sales data."
            )
        else:
            summary = (
                "Ответ основан на результатах инструментов."
                if ru
                else "The answer is based on the tool results."
            )
        report = AnalysisReport(
            language=self.case.language,
            summary=summary,
            facts=facts,
            hypotheses=[],
            recommendations=[],
            limitations=[],
        )
        message = {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": report.model_dump_json()}],
        }
        return AgentTurn([message], [], report, self.model)
