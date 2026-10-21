"""/api/reports: save a reproducible report, read it back, list recent ones."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Response

from app.api.dependencies import ReadSession, WriteSession
from app.api.errors import DATABASE_RESPONSES
from app.schemas.reports import ReportList, ReportOut, ReportRequest, ReportSummary
from app.services import reports

router = APIRouter(prefix="/api/reports", tags=["reports"])

NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"description": "Report not found"},
    **DATABASE_RESPONSES,
}


@router.post("", status_code=201, responses=DATABASE_RESPONSES)
def create_report(
    request: Annotated[ReportRequest, Body()],
    session: WriteSession,
    response: Response,
) -> ReportOut:
    """Compute a comparison or anomaly report and store it as a snapshot.

    The answer is 201 with a Location header pointing at the new report.
    """
    report = reports.create_report(session, request)
    session.commit()
    response.headers["Location"] = f"/api/reports/{report.id}"
    return ReportOut.model_validate(report)


@router.get("/{report_id}", responses=NOT_FOUND)
def get_report(report_id: uuid.UUID, session: ReadSession) -> ReportOut:
    """A saved report exactly as it was computed; 404 for an unknown id."""
    report = reports.get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportOut.model_validate(report)


@router.get("", responses=DATABASE_RESPONSES)
def list_reports(
    session: ReadSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReportList:
    """Saved reports newest first, without result bodies."""
    items = reports.list_reports(session, limit, offset)
    return ReportList(
        items=[ReportSummary.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
    )
