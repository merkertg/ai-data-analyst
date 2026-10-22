"""GET /api/analytics/*: contributions by group and anomaly candidates."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.auth import AUTH_RESPONSES, get_principal
from app.api.dependencies import ReadSession
from app.api.errors import DATABASE_RESPONSES
from app.schemas.analytics import (
    AnomalyQuery,
    AnomalyReportResponse,
    ComparisonQuery,
    ContributionsResponse,
)
from app.services import analytics

# Stage 09: every route needs a valid API token (any role reads).
router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_principal)],
    responses=AUTH_RESPONSES,
)


@router.get("/categories", responses=DATABASE_RESPONSES)
def categories(
    session: ReadSession, query: Annotated[ComparisonQuery, Query()]
) -> ContributionsResponse:
    """Net revenue change between two periods and each category's share of it."""
    return analytics.group_contributions(session, query, "category")


@router.get("/regions", responses=DATABASE_RESPONSES)
def regions(
    session: ReadSession, query: Annotated[ComparisonQuery, Query()]
) -> ContributionsResponse:
    """Net revenue change between two periods and each region's share of it."""
    return analytics.group_contributions(session, query, "region")


@router.get("/anomalies", responses=DATABASE_RESPONSES)
def anomalies(
    session: ReadSession, query: Annotated[AnomalyQuery, Query()]
) -> AnomalyReportResponse:
    """Statistical and Isolation Forest candidates for full months of a period.

    The detector reads only stored sales and stock; it never sees the
    evaluation answers. A candidate is a reason to look, not a proven cause.
    """
    return analytics.anomalies(session, query)
