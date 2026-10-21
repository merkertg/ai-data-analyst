"""The tool-calling loop: model → validated tools → verified report.

The runtime enforces model-turn, tool-call and correction limits, and checks a
deadline between operations. Synchronous SQL already in progress is not
interrupted. A report is accepted only after the evidence check passes.
"""

import json
import time
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from app.agents.contracts import (
    AgentOutcome,
    AgentProgress,
    AgentProvider,
    AgentTurn,
    TokenUsage,
    ToolTrace,
)
from app.agents.evidence import check_report
from app.agents.prompts import correction_message, first_message
from app.agents.tools import TOOL_DEFINITIONS
from app.analytics.models import MOSCOW
from app.llm.config import LLMSettings
from app.llm.errors import (
    AgentContextTooLongError,
    AgentInvalidTurnError,
    AgentStepLimitError,
    AgentTimeoutError,
    AgentToolLimitError,
    AgentUnverifiedReportError,
)

# The whole transcript is sent on every turn (no server-side conversation).
MAX_TRANSCRIPT_CHARACTERS = 120_000
ToolRunner = Callable[[str, str], tuple[dict[str, Any], dict[str, Any]]]


def moscow_today() -> date:
    """The current date in the company's reporting time zone."""
    return datetime.now(MOSCOW).date()


class AgentRuntime:
    """Run one question to a verified report within fixed budgets."""

    def __init__(
        self,
        provider: AgentProvider,
        run_tool: ToolRunner,
        settings: LLMSettings,
        *,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], date] = moscow_today,
    ) -> None:
        """No network or SQL here: everything happens in run()."""
        self.provider = provider
        self.run_tool = run_tool
        self.settings = settings
        self.clock = clock
        self.today = today
        # Public so the caller can store a partial trace when run() fails.
        self.progress = AgentProgress()

    def _remaining(self, deadline: float) -> float:
        """Seconds left in the run; none left is a timeout."""
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise AgentTimeoutError()
        return remaining

    def _check_transcript(self, history: list[dict[str, Any]]) -> None:
        """Stop before sending more context than allowed."""
        size = len(json.dumps(history, ensure_ascii=False))
        if size > MAX_TRANSCRIPT_CHARACTERS:
            raise AgentContextTooLongError()

    def _add_usage(self, usage: TokenUsage | None) -> None:
        """Sum the tokens of every turn, including rejected reports."""
        if usage is None:
            return
        previous = self.progress.usage or TokenUsage(0, 0, 0)
        self.progress.usage = TokenUsage(
            previous.input_tokens + usage.input_tokens,
            previous.output_tokens + usage.output_tokens,
            previous.total_tokens + usage.total_tokens,
        )

    def _validate_turn(self, turn: AgentTurn, seen_ids: set[str]) -> None:
        """Check the whole batch before running any of its calls."""
        if bool(turn.calls) == (turn.report is not None) or not turn.model:
            raise AgentInvalidTurnError()
        batch = [call.call_id for call in turn.calls]
        if (
            any(not value.strip() or len(value) > 200 for value in batch)
            or len(batch) != len(set(batch))
            or any(value in seen_ids for value in batch)
        ):
            raise AgentInvalidTurnError()
        if len(seen_ids) + len(batch) > self.settings.agent_max_tool_calls:
            raise AgentToolLimitError()

    def run(self, question: str) -> AgentOutcome:
        """Answer one question; raise an LLMError subclass on any failure."""
        self.progress = AgentProgress()
        deadline = self.clock() + self.settings.agent_timeout_seconds
        history: list[dict[str, Any]] = [first_message(question, self.today())]
        seen_ids: set[str] = set()
        self._check_transcript(history)
        for _ in range(self.settings.agent_max_steps):
            remaining = self._remaining(deadline)
            self.progress.steps += 1
            turn = self.provider.next_turn(history, TOOL_DEFINITIONS, remaining)
            self._add_usage(turn.usage)
            self._remaining(deadline)
            self._validate_turn(turn, seen_ids)
            # Keep every output item, including reasoning: with store=False the
            # requests do not use a stored response as continuation state.
            history.extend(turn.output_items)
            self._check_transcript(history)
            if turn.report is not None:
                problems = check_report(turn.report, self.progress.tool_trace)
                if not problems:
                    return AgentOutcome(
                        report=turn.report,
                        provider=self.provider.provider,
                        model=turn.model,
                        progress=self.progress,
                    )
                if self.progress.corrections >= self.settings.agent_max_corrections:
                    raise AgentUnverifiedReportError()
                self.progress.corrections += 1
                history.append(correction_message(problems))
                self._check_transcript(history)
                continue
            for call in turn.calls:
                seen_ids.add(call.call_id)
                self._remaining(deadline)
                arguments, result = self.run_tool(call.name, call.arguments)
                self.progress.tool_trace.append(
                    ToolTrace(call.call_id, call.name, arguments, result)
                )
                history.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )
            self._check_transcript(history)
        raise AgentStepLimitError()
