"""GET /api/metrics/*: revenue and order metrics for a period."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.auth import AUTH_RESPONSES, get_principal
from app.api.dependencies import ReadSession
from app.api.errors import DATABASE_RESPONSES
from app.schemas.analytics import (
    OptionalComparisonQuery,
    OrdersResponse,
    RevenueResponse,
)
from app.services import analytics

# Stage 09: every route needs a valid API token (any role reads).
router = APIRouter(
    prefix="/api/metrics",
    tags=["metrics"],
    dependencies=[Depends(get_principal)],
    responses=AUTH_RESPONSES,
)


@router.get("/revenue", responses=DATABASE_RESPONSES)
def revenue(
    session: ReadSession, query: Annotated[OptionalComparisonQuery, Query()]
) -> RevenueResponse:
    """Paid sales, processed refunds and net revenue for [start, end).

    Optional compare_start and compare_end add exact and percentage changes.
    Monthly buckets cover the period; money values are JSON strings.
    """
    return analytics.revenue(session, query)


@router.get("/orders", responses=DATABASE_RESPONSES)
def orders(
    session: ReadSession, query: Annotated[OptionalComparisonQuery, Query()]
) -> OrdersResponse:
    """Paid order count and average order value (before refunds) for a period."""
    return analytics.orders(session, query)
