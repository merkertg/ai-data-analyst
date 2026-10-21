"""Types shared by the runtime, the providers and the tool executor."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

from app.agents.schemas import AnalysisReport

ProviderName = Literal["mock", "openai"]


@dataclass(frozen=True)
class ToolCall:
    """One function call requested by the model; arguments stay raw JSON text."""

    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ToolTrace:
    """A call that the server actually executed, with validated arguments."""

    call_id: str
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass(frozen=True)
class TokenUsage:
    """Tokens reported by the provider; the mock provider reports none."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class AgentProgress:
    """Everything a run did, kept even when the run fails half-way."""

    steps: int = 0
    corrections: int = 0
    tool_trace: list[ToolTrace] = field(default_factory=list)
    usage: TokenUsage | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready snapshot for the agent_runs table."""
        return {
            "steps": self.steps,
            "corrections": self.corrections,
            "tool_calls": [asdict(item) for item in self.tool_trace],
            "usage": asdict(self.usage) if self.usage is not None else None,
        }


@dataclass(frozen=True)
class AgentTurn:
    """One model answer: either tool calls or a final report, never both.

    output_items are the provider's raw items; they go back into the next
    request unchanged so the model sees its own previous turn.
    """

    output_items: list[dict[str, Any]]
    calls: list[ToolCall]
    report: AnalysisReport | None
    model: str
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class AgentOutcome:
    """A verified report and the trace of how it was produced."""

    report: AnalysisReport
    provider: ProviderName
    model: str
    progress: AgentProgress


class AgentProvider(Protocol):
    """A language model behind one method; the runtime owns the loop."""

    provider: ProviderName
    model: str

    def next_turn(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        remaining_seconds: float,
    ) -> AgentTurn:
        """Return the next tool calls or the final report."""
        ...
