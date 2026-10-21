"""The tool-calling loop with a scripted model: no network, no database."""

import json
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from app.agents.contracts import AgentTurn, ProviderName, TokenUsage, ToolCall
from app.agents.runtime import AgentRuntime
from app.agents.schemas import AnalysisReport, Evidence, Fact
from app.llm.config import LLMSettings
from app.llm.errors import (
    AgentContextTooLongError,
    AgentInvalidTurnError,
    AgentStepLimitError,
    AgentTimeoutError,
    AgentToolLimitError,
    AgentUnverifiedReportError,
)

NET_CHANGE = {"ok": True, "data": {"net_revenue": {"absolute": "-291500.00"}}}


class ScriptedProvider:
    """Return prepared turns in order and remember every history it saw."""

    provider: ProviderName = "mock"
    model = "scripted"

    def __init__(self, turns: list[AgentTurn]) -> None:
        self.turns = iter(turns)
        self.histories: list[list[dict[str, Any]]] = []

    def next_turn(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        remaining_seconds: float,
    ) -> AgentTurn:
        self.histories.append(list(history))
        return next(self.turns)


def calls(*items: tuple[str, str]) -> AgentTurn:
    """A turn requesting tools: (call_id, name) pairs with empty arguments."""
    batch = [ToolCall(call_id, name, "{}") for call_id, name in items]
    output = [
        {
            "type": "function_call",
            "call_id": c.call_id,
            "name": c.name,
            "arguments": "{}",
        }
        for c in batch
    ]
    return AgentTurn(output, batch, None, "scripted", TokenUsage(10, 5, 15))


def final(value: str = "-291500.00", call_id: str = "call_1") -> AgentTurn:
    """A turn with a one-fact report citing net_revenue.absolute."""
    report = AnalysisReport(
        language="ru",
        summary="Выручка снизилась.",
        facts=[
            Fact(
                statement=f"Изменение чистой выручки: {value}.",
                evidence=[
                    Evidence(call_id=call_id, field="net_revenue.absolute", value=value)
                ],
            )
        ],
        hypotheses=[],
        recommendations=[],
        limitations=[],
    )
    message = {"type": "message", "role": "assistant", "content": []}
    return AgentTurn([message], [], report, "scripted", TokenUsage(20, 10, 30))


def tools(name: str, arguments: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fake tools: get_revenue answers, anything else is unknown."""
    if name == "get_revenue":
        return {"start": "2026-10-01"}, NET_CHANGE
    return {}, {"ok": False, "error": {"code": "unknown_tool", "message": "no"}}


def runtime(
    provider: ScriptedProvider, run_tool: Any = tools, **limits: Any
) -> AgentRuntime:
    """A runtime with explicit limits and a fixed date, ignoring .env."""
    settings = LLMSettings(_env_file=None, **limits)
    return AgentRuntime(provider, run_tool, settings, today=lambda: date(2026, 10, 21))


def test_multi_step_run_returns_a_verified_report() -> None:
    """Two tool turns (one with parallel calls), then an accepted report."""
    provider = ScriptedProvider(
        [
            calls(("call_1", "get_revenue")),
            calls(("call_2", "get_coverage"), ("call_3", "get_revenue")),
            final(),
        ]
    )
    agent = runtime(provider)

    outcome = agent.run("Почему упала выручка?")

    assert outcome.report.facts[0].evidence[0].value == "-291500.00"
    assert [item.call_id for item in outcome.progress.tool_trace] == [
        "call_1",
        "call_2",
        "call_3",
    ]
    assert outcome.progress.steps == 3
    assert outcome.progress.usage == TokenUsage(40, 20, 60)
    question = json.loads(provider.histories[0][0]["content"])
    assert question == {
        "question": "Почему упала выручка?",
        "today": "2026-10-21",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
    }
    outputs = [
        item["call_id"]
        for item in provider.histories[2]
        if item.get("type") == "function_call_output"
    ]
    assert outputs == ["call_1", "call_2", "call_3"]


def test_tool_errors_go_back_to_the_model() -> None:
    """An unknown tool is a result the model reads, not a crash of the run."""
    provider = ScriptedProvider(
        [calls(("call_9", "drop_table")), calls(("call_1", "get_revenue")), final()]
    )

    outcome = runtime(provider).run("Вопрос")

    assert outcome.progress.tool_trace[0].result["ok"] is False
    error_output = provider.histories[1][-1]
    assert error_output["call_id"] == "call_9"
    assert "unknown_tool" in error_output["output"]


def test_an_unsupported_report_gets_one_correction() -> None:
    """A wrong value is sent back with the problems; the fixed report passes."""
    provider = ScriptedProvider(
        [calls(("call_1", "get_revenue")), final("-300000.00"), final()]
    )

    outcome = runtime(provider).run("Вопрос")

    assert outcome.progress.corrections == 1
    correction = provider.histories[2][-1]
    assert correction["role"] == "user"
    assert "not '-300000.00'" in correction["content"]


def test_a_report_that_stays_unsupported_fails() -> None:
    """After the allowed corrections the run stops with a safe error."""
    provider = ScriptedProvider(
        [calls(("call_1", "get_revenue"))] + [final("-1.00")] * 3
    )
    agent = runtime(provider, agent_max_corrections=1)

    with pytest.raises(AgentUnverifiedReportError):
        agent.run("Вопрос")
    assert agent.progress.corrections == 1
    assert len(agent.progress.tool_trace) == 1


def test_step_limit_stops_an_endless_investigation() -> None:
    """A model that never reports is stopped after agent_max_steps turns."""
    provider = ScriptedProvider(
        [calls((f"call_{index}", "get_revenue")) for index in range(10)]
    )
    agent = runtime(provider, agent_max_steps=3)

    with pytest.raises(AgentStepLimitError):
        agent.run("Вопрос")
    assert agent.progress.steps == 3
    assert len(agent.progress.tool_trace) == 3


def test_tool_limit_rejects_the_whole_batch() -> None:
    """No call of an over-limit batch runs: the check comes first."""
    executed: list[str] = []

    def counting(name: str, arguments: str) -> tuple[dict[str, Any], dict[str, Any]]:
        executed.append(name)
        return tools(name, arguments)

    provider = ScriptedProvider(
        [
            calls(("call_1", "get_revenue")),
            calls(("call_2", "get_revenue"), ("call_3", "get_revenue")),
        ]
    )
    agent = runtime(provider, counting, agent_max_tool_calls=2)

    with pytest.raises(AgentToolLimitError):
        agent.run("Вопрос")
    assert executed == ["get_revenue"]


@pytest.mark.parametrize(
    "turn",
    [
        calls(("call_1", "get_revenue"), ("call_1", "get_revenue")),
        AgentTurn([], [ToolCall("call_1", "get_revenue", "{}")], final().report, "x"),
        AgentTurn([], [], None, "x"),
    ],
    ids=["duplicate call id", "calls and report", "neither"],
)
def test_invalid_turns_are_rejected(turn: AgentTurn) -> None:
    """A turn is tool calls or a report, with unique call ids."""
    with pytest.raises(AgentInvalidTurnError):
        runtime(ScriptedProvider([turn])).run("Вопрос")


def test_a_reused_call_id_is_rejected() -> None:
    """A call id from an earlier turn cannot be answered twice."""
    provider = ScriptedProvider(
        [calls(("call_1", "get_revenue")), calls(("call_1", "get_revenue"))]
    )

    with pytest.raises(AgentInvalidTurnError):
        runtime(provider).run("Вопрос")


def test_timeout_covers_the_whole_run() -> None:
    """The clock runs out between turns: the run stops with a timeout."""
    ticks: Iterator[float] = iter([0.0, 1.0, 2.0, 200.0, 201.0])
    provider = ScriptedProvider([calls(("call_1", "get_revenue")), final()])
    settings = LLMSettings(_env_file=None, agent_timeout_seconds=100)
    agent = AgentRuntime(
        provider, tools, settings, clock=lambda: next(ticks), today=lambda: date.today()
    )

    with pytest.raises(AgentTimeoutError):
        agent.run("Вопрос")


def test_context_limit_stops_huge_tool_results() -> None:
    """The transcript size is checked before it is sent again."""

    def huge(name: str, arguments: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return {}, {"ok": True, "data": {"text": "x" * 130_000}}

    provider = ScriptedProvider([calls(("call_1", "get_revenue")), final()])

    with pytest.raises(AgentContextTooLongError):
        runtime(provider, huge).run("Вопрос")
