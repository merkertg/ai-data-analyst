"""Exercise HTTP contracts and safe failures using an in-memory transport."""

import io
import json
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import BaseHandler, ProxyHandler, Request, build_opener
from urllib.response import addinfourl

import pytest

from app.analytics.models import Dimension
from app.schemas.analytics import AnomalyQuery, ComparisonQuery
from app.schemas.reports import AnomalyReportRequest, ComparisonReportRequest
from ui.client import MAX_RESPONSE_BYTES, APIClient, APIError, _NoRedirects
from ui.config import UISettings


class MemoryResponse(io.BytesIO):
    """An HTTP-like response that records how much the client asks to read."""

    status = 200

    def __init__(self, payload: bytes) -> None:
        """Keep response bytes and the requested read sizes for the cap check."""
        super().__init__(payload)
        self.read_sizes: list[int | None] = []

    def read(self, size: int | None = -1) -> bytes:
        """Record each read instead of allocating a real network response."""
        self.read_sizes.append(size)
        return super().read(size)


class MemoryTransport:
    """A replaceable opener which never opens a socket."""

    def __init__(self, payload: object = None) -> None:
        """Encode a JSON response or use raw bytes to simulate invalid bodies."""
        self.payload = (
            payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        )
        self.calls: list[tuple[Request, float]] = []
        self.error: Exception | None = None
        self.response: MemoryResponse | None = None

    def open(self, request: Request, *, timeout: float) -> MemoryResponse:
        """Return a fresh response or raise the configured transport failure."""
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        self.response = MemoryResponse(self.payload)
        return self.response


@pytest.fixture
def connect(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[object], tuple[APIClient, MemoryTransport]]:
    """Build clients whose open method is replaced before any request occurs."""

    def make(payload: object = None) -> tuple[APIClient, MemoryTransport]:
        client = APIClient(UISettings(_env_file=None))
        transport = MemoryTransport(payload)
        monkeypatch.setattr(client._opener, "open", transport.open)
        return client, transport

    return make


@pytest.fixture
def comparison() -> ComparisonQuery:
    """Use explicit half-open dates for deterministic endpoint serialization."""
    return ComparisonQuery(
        start=date(2026, 9, 1),
        end=date(2026, 10, 1),
        compare_start=date(2026, 8, 1),
        compare_end=date(2026, 9, 1),
    )


def test_readiness_and_timeout_are_forwarded(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """Validate readiness rather than trusting arbitrary successful JSON."""
    client, transport = connect({"status": "ready", "revision": "0003"})
    assert client.ready() == {"status": "ready", "revision": "0003"}
    request, timeout = transport.calls[0]
    assert request.full_url == "http://127.0.0.1:8000/ready"
    assert request.get_method() == "GET"
    assert timeout == 150


def test_revenue_preserves_decimal_money_and_null_percent(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
    comparison: ComparisonQuery,
) -> None:
    """HTTP JSON strings stay exact Decimal values and null stays unavailable."""
    period = {"start": "2026-09-01", "end": "2026-10-01"}
    client, transport = connect(
        {
            "period": period,
            "paid_sales": "9007199254740993.01",
            "refunds": "0.01",
            "net_revenue": "9007199254740993.00",
            "monthly": [],
            "comparison": None,
        }
    )
    result = client.revenue(comparison)
    assert result.paid_sales == Decimal("9007199254740993.01")
    assert result.comparison is None
    parsed = urlsplit(transport.calls[0][0].full_url)
    assert parsed.path == "/api/metrics/revenue"
    assert parse_qs(parsed.query) == {
        "start": ["2026-09-01"],
        "end": ["2026-10-01"],
        "compare_start": ["2026-08-01"],
        "compare_end": ["2026-09-01"],
    }


def test_orders_keep_undefined_aov(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
    comparison: ComparisonQuery,
) -> None:
    """An empty period must not become a fabricated zero-valued average."""
    client, _ = connect(
        {
            "period": {"start": "2026-09-01", "end": "2026-10-01"},
            "paid_orders": 0,
            "average_order_value": None,
            "monthly": [],
            "comparison": None,
        }
    )
    assert client.orders(comparison).average_order_value is None


def test_create_run_serializes_only_the_validated_question(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """Submitting a question is a single POST with no provider settings or keys."""
    client, transport = connect({})
    with pytest.raises(APIError, match="invalid response"):
        client.create_run("  Почему упала выручка?  ")
    request, _ = transport.calls[0]
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert isinstance(request.data, bytes)
    assert json.loads(request.data) == {"question": "Почему упала выручка?"}
    assert len(transport.calls) == 1


def test_invalid_question_does_not_use_transport(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """Locally invalid questions are rejected without a database or network call."""
    client, transport = connect(None)
    with pytest.raises(APIError) as caught:
        client.create_run("  ")
    assert caught.value.status_code == 422
    assert not transport.calls


@pytest.mark.parametrize("kind", ["comparison", "anomalies"])
def test_save_report_sends_the_discriminated_payload_once(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
    comparison: ComparisonQuery,
    kind: str,
) -> None:
    """The client saves via the API rather than importing or recomputing services."""
    request: ComparisonReportRequest | AnomalyReportRequest
    if kind == "comparison":
        request = ComparisonReportRequest(
            **comparison.model_dump(), kind="comparison", dimension="region"
        )
    else:
        request = AnomalyReportRequest(
            kind="anomalies", start=date(2026, 1, 1), end=date(2026, 10, 1), seed=17
        )
    client, transport = connect({})
    with pytest.raises(APIError, match="invalid response"):
        client.create_report(request)
    sent, _ = transport.calls[0]
    assert sent.get_method() == "POST"
    assert sent.full_url.endswith("/api/reports")
    assert isinstance(sent.data, bytes)
    assert json.loads(sent.data) == request.model_dump(mode="json")
    assert len(transport.calls) == 1


@pytest.mark.parametrize("kind", ["runs", "reports"])
def test_history_uses_pagination_without_inventing_a_total(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]], kind: str
) -> None:
    """Return validated list envelopes and preserve the requested page offset."""
    client, transport = connect({"items": [], "limit": 7, "offset": 14})
    result = client.runs(7, 14) if kind == "runs" else client.reports(7, 14)
    assert result.items == []
    assert result.limit == 7
    assert result.offset == 14
    assert parse_qs(urlsplit(transport.calls[0][0].full_url).query) == {
        "limit": ["7"],
        "offset": ["14"],
    }


@pytest.mark.parametrize("kind", ["run", "report"])
def test_detail_uses_the_requested_uuid(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]], kind: str
) -> None:
    """History detail requests address exactly the selected immutable record."""
    identifier = uuid.uuid4()
    client, transport = connect({})
    with pytest.raises(APIError, match="invalid response"):
        if kind == "run":
            client.run(identifier)
        else:
            client.report(identifier)
    assert transport.calls[0][0].full_url.endswith(f"/{identifier}")


@pytest.mark.parametrize(
    "status", [301, 307, 308, 400, 404, 413, 422, 500, 502, 503, 504]
)
def test_http_errors_never_expose_server_text_or_retry(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]], status: int
) -> None:
    """Raw API details, redirect URLs and exception text stay outside the UI."""
    client, transport = connect(None)
    marker = "private-password-in-an-error"
    transport.error = HTTPError(
        f"https://user:{marker}@example.com",
        status,
        marker,
        Message(),
        io.BytesIO(json.dumps({"detail": marker}).encode()),
    )
    with pytest.raises(APIError) as caught:
        client.ready()
    assert caught.value.status_code == status
    assert caught.value.run_id is None
    assert marker not in str(caught.value)
    assert marker not in caught.value.message
    assert len(transport.calls) == 1


@pytest.mark.parametrize("status", [413, 502, 503, 504])
def test_handled_failure_retains_only_a_valid_run_uuid(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]], status: int
) -> None:
    """A recoverable failed trace remains accessible without exposing its error."""
    identifier = uuid.uuid4()
    client, transport = connect(None)
    transport.error = HTTPError(
        "http://localhost",
        status,
        "private",
        Message(),
        io.BytesIO(
            json.dumps({"detail": "private", "run_id": str(identifier)}).encode()
        ),
    )
    with pytest.raises(APIError) as caught:
        client.ready()
    assert caught.value.run_id == identifier


@pytest.mark.parametrize("run_id", ["not-a-uuid", 123, None, {}, []])
def test_invalid_failure_run_id_is_ignored(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]], run_id: object
) -> None:
    """Untrusted failure metadata cannot become a path or a UI exception."""
    client, transport = connect(None)
    transport.error = HTTPError(
        "http://localhost",
        502,
        "private",
        Message(),
        io.BytesIO(json.dumps({"run_id": run_id}).encode()),
    )
    with pytest.raises(APIError) as caught:
        client.ready()
    assert caught.value.run_id is None


@pytest.mark.parametrize(
    "error",
    [
        URLError("private-connection-string"),
        URLError(TimeoutError("private-timeout")),
        TimeoutError("private-timeout"),
        ConnectionError("private-connection-string"),
    ],
)
def test_transport_failures_are_safe_and_are_not_retried(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]], error: Exception
) -> None:
    """A timed-out POST may have completed, so the client must never repeat it."""
    client, transport = connect(None)
    transport.error = error
    with pytest.raises(APIError) as caught:
        client.create_run("Why did revenue drop?")
    assert caught.value.status_code is None
    assert "private" not in str(caught.value)
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "payload",
    [b"not-json-with-private-data", b"\xff", b"[]", b'{"status":"ready"}'],
)
def test_invalid_json_or_schema_maps_to_a_safe_error(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]], payload: bytes
) -> None:
    """A 200 status does not bypass JSON and response schema validation."""
    client, _ = connect(payload)
    with pytest.raises(APIError, match="The API returned an invalid response"):
        client.ready()


def test_response_size_is_bounded_before_json_parsing(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """Read at most the documented eight-megabyte cap plus one sentinel byte."""
    client, transport = connect(b" " * (MAX_RESPONSE_BYTES + 100))
    with pytest.raises(APIError, match="too large"):
        client.ready()
    assert transport.response is not None
    assert transport.response.read_sizes == [MAX_RESPONSE_BYTES + 1]


def test_error_response_size_is_also_bounded(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """Error bodies cannot bypass the memory bound or supply unparsed metadata."""
    client, transport = connect(None)
    identifier = uuid.uuid4()
    body = json.dumps({"run_id": str(identifier)}).encode()
    response = MemoryResponse(body + b" " * MAX_RESPONSE_BYTES)
    transport.error = HTTPError("http://localhost", 502, "private", Message(), response)
    with pytest.raises(APIError) as caught:
        client.ready()
    assert caught.value.run_id is None
    assert response.read_sizes == [MAX_RESPONSE_BYTES + 1]


def test_deeply_nested_error_json_does_not_escape_the_error_boundary(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """Even malformed error JSON is discarded rather than shown or re-raised."""
    client, transport = connect(None)
    transport.error = HTTPError(
        "http://localhost",
        502,
        "private",
        Message(),
        io.BytesIO(b"[" * 2000 + b"]" * 2000),
    )
    with pytest.raises(APIError) as caught:
        client.ready()
    assert caught.value.run_id is None


def test_valid_saved_report_keeps_exact_result_strings(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """A saved snapshot is returned without float conversion or recomputation."""
    identifier = uuid.uuid4()
    client, _ = connect(
        {
            "id": str(identifier),
            "kind": "comparison",
            "created_at": "2026-10-21T12:00:00Z",
            "app_version": "0.1.0",
            "parameters": {"dimension": "category"},
            "result": {"net_revenue": "9007199254740993.01"},
        }
    )
    report = client.report(identifier)
    assert report.id == identifier
    assert report.result["net_revenue"] == "9007199254740993.01"


def test_valid_agent_run_keeps_report_evidence_and_trace(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """The UI receives the structured report and its separate tool evidence."""
    identifier = uuid.uuid4()
    client, _ = connect(
        {
            "id": str(identifier),
            "question": "Why did revenue fall?",
            "status": "completed",
            "provider": "mock",
            "model": "mock-analyst-v1",
            "duration_ms": 150,
            "created_at": "2026-10-21T12:00:00Z",
            "report": {
                "language": "en",
                "summary": "Net revenue fell.",
                "facts": [
                    {
                        "statement": "Revenue changed by -10 RUB.",
                        "evidence": [
                            {"call_id": "compare", "field": "change", "value": "-10"}
                        ],
                    }
                ],
                "hypotheses": [],
                "recommendations": [],
                "limitations": ["Demonstration provider."],
            },
            "error": None,
            "steps": 4,
            "corrections": 0,
            "tool_calls": [
                {
                    "call_id": "compare",
                    "name": "compare_periods",
                    "arguments": {},
                    "result": {"ok": True, "data": {"change": "-10"}},
                }
            ],
            "usage": None,
            "app_version": "0.1.0",
        }
    )
    run = client.run(identifier)
    assert run.provider == "mock"
    assert run.report is not None
    assert run.report.facts[0].evidence[0].value == "-10"
    assert run.tool_calls[0].result["data"]["change"] == "-10"


@pytest.mark.parametrize("dimension", ["category", "region"])
def test_contributions_use_the_requested_dimension(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
    comparison: ComparisonQuery,
    dimension: str,
) -> None:
    """Both supported dimensions map to fixed API paths, never a generic URL."""
    typed_dimension: Dimension = "category" if dimension == "category" else "region"
    client, transport = connect({})
    with pytest.raises(APIError, match="invalid response"):
        client.contributions(comparison, typed_dimension)
    ending = "categories" if dimension == "category" else "regions"
    assert urlsplit(transport.calls[0][0].full_url).path.endswith(f"/{ending}")


def test_redirect_handler_never_builds_a_second_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A loopback server cannot redirect this client to an external address."""

    class RedirectReply(addinfourl):
        """A synthetic redirect response for urllib's real processing chain."""

        msg = "Found"

    class RedirectTransport(BaseHandler):
        """Intercept HTTP before the real network handler can open a socket."""

        handler_order = 0

        def __init__(self) -> None:
            """Record requests to detect any attempted follow-up request."""
            self.calls: list[str] = []

        def http_open(self, request: Request) -> RedirectReply:
            """Return the redirect without using DNS or a network connection."""
            self.calls.append(request.full_url)
            headers = Message()
            headers["Location"] = "http://external.example/private"
            return RedirectReply(io.BytesIO(b""), headers, request.full_url, 302)

    transport = RedirectTransport()
    client = APIClient(UISettings(_env_file=None))
    monkeypatch.setattr(
        client,
        "_opener",
        build_opener(ProxyHandler({}), _NoRedirects(), transport),
    )
    with pytest.raises(APIError) as caught:
        client.ready()
    assert caught.value.status_code == 302
    assert transport.calls == ["http://127.0.0.1:8000/ready"]


def test_proxy_environment_does_not_configure_the_opener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even configured environment proxies cannot see local questions or reports."""
    monkeypatch.setenv("HTTP_PROXY", "http://private-proxy.example:8888")
    monkeypatch.setenv("HTTPS_PROXY", "http://private-proxy.example:8888")

    def refuse_environment_lookup() -> dict[str, str]:
        """Fail if urllib ever asks the environment for proxy credentials."""
        raise AssertionError("The UI client must not load environment proxies")

    monkeypatch.setattr("urllib.request.getproxies", refuse_environment_lookup)
    APIClient(UISettings(_env_file=None))


def test_anomaly_parameters_retain_the_seed(
    connect: Callable[[object], tuple[APIClient, MemoryTransport]],
) -> None:
    """Anomaly requests retain reproducible interval and detector seed parameters."""
    client, transport = connect({})
    with pytest.raises(APIError, match="invalid response"):
        client.anomalies(
            AnomalyQuery(start=date(2026, 1, 1), end=date(2026, 10, 1), seed=17)
        )
    parsed = urlsplit(transport.calls[0][0].full_url)
    assert parsed.path == "/api/analytics/anomalies"
    assert parse_qs(parsed.query)["seed"] == ["17"]
