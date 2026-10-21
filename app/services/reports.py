"""Create, read and list saved reports.

A report is a snapshot: the result is computed once, stored as JSON and never
recomputed. The request parameters and the code version are stored with it, so
the same report can be reproduced on the same data.
"""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.db.models import Report, ReportKind
from app.schemas.reports import (
    AnomalyReportRequest,
    ComparisonReportRequest,
)
from app.services import analytics


def create_report(
    session: Session, request: ComparisonReportRequest | AnomalyReportRequest
) -> Report:
    """Compute the requested result and add it as a new report row.

    The caller commits: the route decides the transaction boundary, and a
    failed calculation leaves nothing behind.
    """
    result: BaseModel
    if isinstance(request, ComparisonReportRequest):
        result = analytics.group_contributions(session, request, request.dimension)
        kind = ReportKind.COMPARISON
    else:
        result = analytics.anomalies(session, request)
        kind = ReportKind.ANOMALIES
    report = Report(
        kind=kind,
        # mode="json": dates and Decimal become strings, exactly as in the API.
        parameters=request.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
        app_version=__version__,
    )
    session.add(report)
    session.flush()
    # created_at comes from PostgreSQL now(); read it back for the response.
    session.refresh(report)
    return report


def get_report(session: Session, report_id: uuid.UUID) -> Report | None:
    """One report by id, or None when it does not exist."""
    return session.get(Report, report_id)


def list_reports(session: Session, limit: int, offset: int) -> list[Report]:
    """A page of reports, newest first; id breaks ties for a stable order."""
    query = (
        select(Report)
        .order_by(Report.created_at.desc(), Report.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(query))
