"""Requests and responses for saved, reproducible analytics reports."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.analytics.models import Dimension
from app.schemas.analytics import AnomalyQuery, ComparisonQuery


class ComparisonReportRequest(ComparisonQuery):
    """Save a period comparison with category or regional contributions."""

    kind: Literal["comparison"]
    dimension: Dimension = "category"


class AnomalyReportRequest(AnomalyQuery):
    """Save an anomaly detection run for a period."""

    kind: Literal["anomalies"]


# The "kind" field selects the request model; an unknown kind is a 422 error.
ReportRequest = Annotated[
    ComparisonReportRequest | AnomalyReportRequest, Field(discriminator="kind")
]


class ReportSummary(BaseModel):
    """A saved report without its result body, for lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["comparison", "anomalies"]
    created_at: datetime
    app_version: str
    parameters: dict[str, Any]


class ReportOut(ReportSummary):
    """A saved report with its frozen result; money values are JSON strings."""

    result: dict[str, Any]


class ReportList(BaseModel):
    """One page of saved reports, newest first."""

    items: list[ReportSummary]
    limit: int
    offset: int
