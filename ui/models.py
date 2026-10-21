"""Session snapshots live in an imported module so reruns keep their types."""

from dataclasses import dataclass

from app.analytics.models import Dimension
from app.schemas.agents import AgentRunOut
from app.schemas.analytics import (
    ComparisonQuery,
    ContributionsResponse,
    OrdersResponse,
    RevenueResponse,
)


@dataclass(frozen=True)
class DashboardSnapshot:
    """Keep submitted filters with their responses, apart from edited widgets."""

    query: ComparisonQuery
    dimension: Dimension
    revenue: RevenueResponse
    orders: OrdersResponse
    contributions: ContributionsResponse


@dataclass(frozen=True)
class ChatEntry:
    """One independent question and its stored run, or a public client error."""

    question: str
    run: AgentRunOut | None
    error: str | None = None
