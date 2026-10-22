"""A bounded HTTP client; the interface never imports database services."""

import json
import uuid
from email.message import Message
from http.client import HTTPException
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from pydantic import BaseModel, Field, ValidationError

from app.analytics.models import Dimension
from app.schemas.agents import AgentQuestion, AgentRunList, AgentRunOut
from app.schemas.analytics import (
    AnomalyQuery,
    AnomalyReportResponse,
    ComparisonQuery,
    ContributionsResponse,
    OrdersResponse,
    RevenueResponse,
)
from app.schemas.reports import (
    AnomalyReportRequest,
    ComparisonReportRequest,
    ReportList,
    ReportOut,
)
from ui.config import UISettings

MAX_RESPONSE_BYTES = 8 * 1024 * 1024

_HTTP_MESSAGES = {
    401: "The API token is missing or invalid. Set UI_API_TOKEN and restart.",
    403: "Your API token does not allow this action (analyst role required).",
    404: "The requested record was not found.",
    413: "The analysis exceeded its context limit.",
    422: "The request parameters are invalid.",
    429: "Too many requests for this token. Wait a minute and try again.",
    502: "The agent could not produce a valid report.",
    503: "The API is unavailable or not configured.",
    504: "The analysis timed out. Check history before trying again.",
}


class APIError(Exception):
    """A safe public error, optionally linked to a stored failed agent run."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        run_id: uuid.UUID | None = None,
    ) -> None:
        """Keep only safe client-generated text and validated metadata."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.run_id = run_id


class _NoRedirects(HTTPRedirectHandler):
    """Do not send a local request to a different origin after a redirect."""

    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> None:
        """Let urllib raise HTTPError instead of constructing another request."""
        return None


class _ReadyResponse(BaseModel):
    """The small readiness contract used before loading analytical data."""

    status: Literal["ready"]
    revision: str = Field(min_length=1)


def _failed_run_id(payload: bytes, status_code: int) -> uuid.UUID | None:
    """Read only a valid UUID from a handled agent failure, ignoring its text."""
    if status_code not in {413, 502, 503, 504} or len(payload) > MAX_RESPONSE_BYTES:
        return None
    try:
        body = json.loads(payload)
        if isinstance(body, dict) and isinstance(body.get("run_id"), str):
            return uuid.UUID(body["run_id"])
    except (ValueError, UnicodeError, RecursionError):
        pass
    return None


def _http_error(error: HTTPError) -> APIError:
    """Discard the server's message, URL and exception text before reporting it."""
    try:
        with error:
            payload = error.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, HTTPException):
        payload = b""
    return APIError(
        _HTTP_MESSAGES.get(error.code, "The API request failed."),
        status_code=error.code,
        run_id=_failed_run_id(payload, error.code),
    )


class APIClient:
    """Call only the configured API; no proxies, redirects or automatic retries."""

    def __init__(self, settings: UISettings) -> None:
        """Create a private opener so environment proxy settings are ignored."""
        self.settings = settings
        self._opener = build_opener(ProxyHandler({}), _NoRedirects())

    def _request[T: BaseModel](
        self,
        path: str,
        response_model: type[T],
        *,
        query: BaseModel | dict[str, int] | None = None,
        body: BaseModel | None = None,
    ) -> T:
        """Read a size-bounded JSON response and validate it against its schema."""
        url = f"{self.settings.api_url}{path}"
        if query is not None:
            parameters = (
                query.model_dump(mode="json", exclude_none=True)
                if isinstance(query, BaseModel)
                else query
            )
            url = f"{url}?{urlencode(parameters)}"
        data = body.model_dump_json().encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if self.settings.api_token is not None:
            # The token goes only to the configured local API origin.
            token = self.settings.api_token.get_secret_value()
            headers["Authorization"] = f"Bearer {token}"
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers)
        try:
            with self._opener.open(
                request, timeout=self.settings.request_timeout_seconds
            ) as response:
                status_code = response.status
                if not isinstance(status_code, int) or not 200 <= status_code < 300:
                    raise APIError("The API request failed.")
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            raise _http_error(error) from None
        except TimeoutError:
            raise APIError(
                "The API request timed out. Check history before trying again."
            ) from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise APIError(
                    "The API request timed out. Check history before trying again."
                ) from None
            raise APIError("Cannot reach the API. Check that it is running.") from None
        except (OSError, HTTPException):
            raise APIError("Cannot reach the API. Check that it is running.") from None
        if len(payload) > MAX_RESPONSE_BYTES:
            raise APIError("The API response is too large.", status_code) from None
        try:
            return response_model.model_validate_json(payload)
        except ValidationError:
            raise APIError(
                "The API returned an invalid response.", status_code
            ) from None

    def ready(self) -> dict[str, str]:
        """Check database readiness and return the current schema revision."""
        result = self._request("/ready", _ReadyResponse)
        return {"status": result.status, "revision": result.revision}

    def revenue(self, query: ComparisonQuery) -> RevenueResponse:
        """Get exact revenue and monthly buckets with a comparison period."""
        return self._request("/api/metrics/revenue", RevenueResponse, query=query)

    def orders(self, query: ComparisonQuery) -> OrdersResponse:
        """Get paid order counts and AOV, preserving undefined values."""
        return self._request("/api/metrics/orders", OrdersResponse, query=query)

    def contributions(
        self, query: ComparisonQuery, dimension: Dimension
    ) -> ContributionsResponse:
        """Get signed category or region contributions without recalculating them."""
        paths = {"category": "categories", "region": "regions"}
        return self._request(
            f"/api/analytics/{paths[dimension]}", ContributionsResponse, query=query
        )

    def anomalies(self, query: AnomalyQuery) -> AnomalyReportResponse:
        """Get anomaly candidates for the selected interval and deterministic seed."""
        return self._request(
            "/api/analytics/anomalies", AnomalyReportResponse, query=query
        )

    def create_run(self, question: str) -> AgentRunOut:
        """Submit one independent investigation exactly once."""
        try:
            body = AgentQuestion(question=question)
        except ValidationError:
            raise APIError("The request parameters are invalid.", 422) from None
        return self._request("/api/agent/runs", AgentRunOut, body=body)

    def runs(self, limit: int = 20, offset: int = 0) -> AgentRunList:
        """List stored investigations without their reports and tool traces."""
        return self._request(
            "/api/agent/runs", AgentRunList, query={"limit": limit, "offset": offset}
        )

    def run(self, run_id: uuid.UUID) -> AgentRunOut:
        """Read one stored investigation, including failed runs and their traces."""
        return self._request(f"/api/agent/runs/{run_id}", AgentRunOut)

    def create_report(
        self, request: ComparisonReportRequest | AnomalyReportRequest
    ) -> ReportOut:
        """Compute and persist one report; the returned body is the saved snapshot."""
        return self._request("/api/reports", ReportOut, body=request)

    def reports(self, limit: int = 20, offset: int = 0) -> ReportList:
        """List saved analytics reports without their result bodies."""
        return self._request(
            "/api/reports", ReportList, query={"limit": limit, "offset": offset}
        )

    def report(self, report_id: uuid.UUID) -> ReportOut:
        """Read an immutable analytics report without recomputing it."""
        return self._request(f"/api/reports/{report_id}", ReportOut)
