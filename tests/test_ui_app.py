"""Exercise Streamlit actions and reruns against typed in-memory API answers."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import Button, DateInput

from app.analytics.models import Dimension
from app.schemas.agents import AgentRunList, AgentRunOut, AgentRunSummary
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
    ReportSummary,
)
from ui.client import APIClient, APIError
from ui.config import UISettings
from ui.models import DashboardSnapshot

APP = Path(__file__).resolve().parents[1] / "ui" / "main.py"
PERIOD = {"start": "2026-09-01", "end": "2026-10-01"}
PREVIOUS = {"start": "2026-08-01", "end": "2026-09-01"}


def revenue_result() -> RevenueResponse:
    """Keep a cent above the float integer precision boundary in the UI sample."""
    return RevenueResponse.model_validate(
        {
            "period": PERIOD,
            "paid_sales": "9007199254740993.01",
            "refunds": "0.01",
            "net_revenue": "9007199254740993.00",
            "monthly": [
                {
                    "period": PERIOD,
                    "paid_sales": "9007199254740993.01",
                    "refunds": "0.01",
                    "net_revenue": "9007199254740993.00",
                }
            ],
            "comparison": None,
        }
    )


def contributions_result() -> ContributionsResponse:
    """Provide an exact comparison snapshot without running analytics or SQL."""
    return ContributionsResponse.model_validate(
        {
            "dimension": "category",
            "current": {
                "period": PERIOD,
                "paid_sales": "9007199254740993.01",
                "refunds": "0.01",
                "net_revenue": "9007199254740993.00",
                "paid_orders": 2,
                "average_order_value": "4503599627370496.51",
            },
            "previous": {
                "period": PREVIOUS,
                "paid_sales": "9007199254740993.51",
                "refunds": "0.01",
                "net_revenue": "9007199254740993.50",
                "paid_orders": 2,
                "average_order_value": "4503599627370496.76",
            },
            "net_revenue": {
                "previous": "9007199254740993.50",
                "current": "9007199254740993.00",
                "absolute": "-0.50",
                "percent": "-0.00",
            },
            "contributions": [
                {
                    "name": "pumps",
                    "current_sales": "9007199254740993.01",
                    "current_refunds": "0.01",
                    "previous_sales": "9007199254740993.51",
                    "previous_refunds": "0.01",
                    "current_net": "9007199254740993.00",
                    "previous_net": "9007199254740993.50",
                    "delta": "-0.50",
                    "contribution_percent": "100.00",
                }
            ],
        }
    )


def investigation(*, failed: bool = False) -> AgentRunOut:
    """Return a stored run with evidence and trace, or a handled public failure."""
    return AgentRunOut.model_validate(
        {
            "id": "00000000-0000-0000-0000-000000000064",
            "question": "Why did revenue change?",
            "status": "failed" if failed else "completed",
            "provider": "mock",
            "model": "demo-planner",
            "duration_ms": 12,
            "created_at": "2026-10-21T10:00:00Z",
            "report": None
            if failed
            else {
                "language": "en",
                "summary": "Net revenue changed by 0.50 RUB.",
                "facts": [
                    {
                        "statement": "The net revenue change was -0.50 RUB.",
                        "evidence": [
                            {
                                "call_id": "comparison-1",
                                "field": "net_revenue.absolute",
                                "value": "-0.50",
                            }
                        ],
                    }
                ],
                "hypotheses": [],
                "recommendations": ["Inspect the affected category."],
                "limitations": ["Demo mode; no language model was called."],
            },
            "error": {"code": "invalid_report", "detail": "The report was invalid."}
            if failed
            else None,
            "steps": 2,
            "corrections": 0,
            "tool_calls": [
                {
                    "call_id": "comparison-1",
                    "name": "compare_periods",
                    "arguments": {"start": "2026-09-01", "end": "2026-10-01"},
                    "result": {"net_revenue": {"absolute": "-0.50"}},
                }
            ],
            "usage": None,
            "app_version": "0.1.0",
        }
    )


class MemoryAPI:
    """Record UI intentions and return deterministic, fully validated responses."""

    def __init__(self) -> None:
        """Keep all mutable test state outside the rerun script module."""
        self.calls: list[tuple[str, object]] = []
        self.errors: dict[str, APIError] = {}
        self.run_result = investigation()
        self.contributions_result = contributions_result()

    def record(self, name: str, payload: object = None) -> None:
        """Raise only an explicitly configured safe API error for this action."""
        self.calls.append((name, payload))
        if name in self.errors:
            raise self.errors[name]

    def ready(self) -> dict[str, str]:
        """Return the schema marker without opening a socket."""
        self.record("ready")
        return {"status": "ready", "revision": "0003"}

    def revenue(self, query: ComparisonQuery) -> RevenueResponse:
        """Return exact revenue for the UI's submitted interval."""
        self.record("revenue", query.model_dump())
        return revenue_result()

    def orders(self, query: ComparisonQuery) -> OrdersResponse:
        """Return order counts independently from revenue arithmetic."""
        self.record("orders", query.model_dump())
        return OrdersResponse.model_validate(
            {
                "period": PERIOD,
                "paid_orders": 2,
                "average_order_value": "4503599627370496.51",
                "monthly": [
                    {
                        "period": PERIOD,
                        "paid_orders": 2,
                        "average_order_value": "4503599627370496.51",
                    }
                ],
                "comparison": None,
            }
        )

    def contributions(
        self, query: ComparisonQuery, dimension: Dimension
    ) -> ContributionsResponse:
        """Return an exact contribution breakdown for the requested dimension."""
        self.record("contributions", (query.model_dump(), dimension))
        return self.contributions_result.model_copy(update={"dimension": dimension})

    def anomalies(self, query: AnomalyQuery) -> AnomalyReportResponse:
        """Return a real-shaped detector envelope without reading answer labels."""
        self.record("anomalies", query.model_dump())
        return AnomalyReportResponse(
            schema_version=1,
            period=query.period(),
            seed=query.seed,
            observations={"monthly": 9},
            configuration={"method": "test"},
            finding_count=0,
            findings=[],
        )

    def create_run(self, question: str) -> AgentRunOut:
        """Record exactly one creation per explicit question submission."""
        self.record("create_run", question)
        return self.run_result.model_copy(update={"question": question})

    def run(self, run_id: UUID) -> AgentRunOut:
        """Opening history reads an existing result and does not investigate."""
        self.record("run", run_id)
        return self.run_result.model_copy(update={"id": run_id})

    def runs(self, limit: int = 20, offset: int = 0) -> AgentRunList:
        """Expose a full first page and an empty next page for navigation."""
        self.record("runs", (limit, offset))
        return AgentRunList(
            items=[
                AgentRunSummary.model_validate(
                    self.run_result.model_copy(update={"id": UUID(int=100 + index)})
                )
                for index in range(limit if offset == 0 else 0)
            ],
            limit=limit,
            offset=offset,
        )

    def create_report(
        self, request: ComparisonReportRequest | AnomalyReportRequest
    ) -> ReportOut:
        """Keep submitted parameters on the returned stored snapshot."""
        self.record("create_report", request.model_dump())
        if isinstance(request, AnomalyReportRequest):
            return ReportOut(
                id=UUID(int=300 << 96),
                kind="anomalies",
                created_at=datetime(2026, 10, 21, 10, tzinfo=UTC),
                app_version="0.1.0",
                parameters=request.model_dump(mode="json"),
                result={
                    "schema_version": 1,
                    "period": {
                        "start": request.start.isoformat(),
                        "end": request.end.isoformat(),
                    },
                    "seed": request.seed,
                    "observations": {"monthly": 9},
                    "configuration": {"method": "test"},
                    "finding_count": 0,
                    "findings": [],
                },
            )
        return self.saved_report(parameters=request.model_dump(mode="json"))

    def saved_report(self, parameters: dict[str, Any] | None = None) -> ReportOut:
        """Build an immutable comparison result with the exact original money."""
        return ReportOut(
            id=UUID(int=200 << 96),
            kind="comparison",
            created_at=datetime(2026, 10, 21, 10, tzinfo=UTC),
            app_version="0.1.0",
            parameters=parameters or {"start": "2026-09-01", "end": "2026-10-01"},
            result=self.contributions_result.model_dump(mode="json"),
        )

    def reports(self, limit: int = 20, offset: int = 0) -> ReportList:
        """Provide stored metadata without recalculating any report body."""
        self.record("reports", (limit, offset))
        return ReportList(
            items=[
                ReportSummary.model_validate(
                    self.saved_report().model_copy(
                        update={"id": UUID(int=(200 + index) << 96)}
                    )
                )
                for index in range(limit if offset == 0 else 0)
            ],
            limit=limit,
            offset=offset,
        )

    def report(self, report_id: UUID) -> ReportOut:
        """Read only the selected immutable result."""
        self.record("report", report_id)
        return self.saved_report().model_copy(update={"id": report_id})


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> MemoryAPI:
    """Replace every client action and disable the developer's real .env."""
    monkeypatch.setitem(UISettings.model_config, "env_file", None)
    monkeypatch.setenv("UI_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("UI_REQUEST_TIMEOUT_SECONDS", "150")
    memory = MemoryAPI()

    def adapter(method: Callable[..., Any]) -> Callable[..., Any]:
        """Bind fake methods to real client instances created by each rerun."""

        def invoke(_client: APIClient, *args: Any, **kwargs: Any) -> Any:
            """Forward the action to shared in-memory state, never to urllib."""
            return method(*args, **kwargs)

        return invoke

    for name in (
        "ready",
        "revenue",
        "orders",
        "contributions",
        "anomalies",
        "create_run",
        "run",
        "runs",
        "create_report",
        "reports",
        "report",
    ):
        monkeypatch.setattr(APIClient, name, adapter(getattr(memory, name)))
    return memory


def button(app: AppTest, label: str) -> Button:
    """Find a visible action by its user-facing label, not its incidental order."""
    return next(item for item in app.button if item.label == label)


def date_input(app: AppTest, label: str) -> DateInput:
    """Address a form date without relying on the layout of other controls."""
    return next(item for item in app.date_input if item.label == label)


def open_app(page: str = "Dashboard") -> AppTest:
    """Start the real script and navigate without requesting data implicitly."""
    app = AppTest.from_file(APP, default_timeout=10).run()
    assert not app.exception
    if page != "Dashboard":
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
    return app


def test_initial_dashboard_does_not_request_any_backend_data(api: MemoryAPI) -> None:
    """Loading a page alone does not run metrics, a model or history queries."""
    app = open_app()
    assert not api.calls
    assert not app.metric
    assert not app.get("plotly_chart")


def test_dashboard_keeps_exact_cards_tables_and_three_charts(api: MemoryAPI) -> None:
    """Large monetary values survive rendering without conversion through float."""
    app = open_app()
    button(app, "Load dashboard").click().run()
    assert not app.exception
    assert [name for name, _ in api.calls] == ["revenue", "orders", "contributions"]
    assert {item.label: item.value for item in app.metric} == {
        "Paid sales": "9 007 199 254 740 993.01 RUB",
        "Refunds": "0.01 RUB",
        "Net revenue": "9 007 199 254 740 993.00 RUB",
        "Paid orders": "2",
        "Average order value": "4 503 599 627 370 496.51 RUB",
    }
    assert len(app.get("plotly_chart")) == 3
    table = app.dataframe[0].value
    assert table.iloc[0]["Current net, RUB"] == "9 007 199 254 740 993.00 RUB"
    app.run()
    assert len(api.calls) == 3


@pytest.mark.parametrize("label", ["Start", "Comparison start"])
def test_invalid_dashboard_dates_stop_before_backend(
    api: MemoryAPI, label: str
) -> None:
    """Reversed current or comparison ranges cannot trigger even the first GET."""
    app = open_app()
    date_input(app, label).set_value(date(2026, 11, 1))
    button(app, "Load dashboard").click().run()
    assert not app.exception
    assert not api.calls
    assert any("Check both date ranges" in item.value for item in app.error)


def test_unsent_edits_do_not_replace_loaded_filters_or_repeat_report_post(
    api: MemoryAPI,
) -> None:
    """Saving uses the submitted snapshot and reruns do not create duplicates."""
    app = open_app()
    button(app, "Load dashboard").click().run()
    date_input(app, "Start").set_value(date(2026, 7, 1))
    app.selectbox[0].set_value("region").run()
    snapshot = cast(DashboardSnapshot, app.session_state["dashboard"])
    assert snapshot.query.start == date(2026, 9, 1)
    assert snapshot.dimension == "category"
    button(app, "Save comparison report").click().run()
    assert not app.exception
    saved = [payload for name, payload in api.calls if name == "create_report"]
    assert saved == [
        {
            "start": date(2026, 9, 1),
            "end": date(2026, 10, 1),
            "compare_start": date(2026, 8, 1),
            "compare_end": date(2026, 9, 1),
            "kind": "comparison",
            "dimension": "category",
        }
    ]
    report = cast(ReportOut, app.session_state["selected_report"])
    assert report.parameters["start"] == "2026-09-01"
    assert report.parameters["dimension"] == "category"
    assert len(app.get("download_button")) == 1
    app.run()
    assert len([name for name, _ in api.calls if name == "create_report"]) == 1


def test_anomaly_save_keeps_submitted_interval_and_seed(api: MemoryAPI) -> None:
    """Unsent detector edits cannot change which analytical snapshot is saved."""
    app = open_app()
    button(app, "Detect anomalies").click().run()
    assert not app.exception
    date_input(app, "Detection start").set_value(date(2026, 2, 1))
    app.number_input[0].set_value(17).run()
    button(app, "Save anomaly report").click().run()
    assert not app.exception
    assert [name for name, _ in api.calls] == ["anomalies", "create_report"]
    saved = cast(dict[str, object], api.calls[-1][1])
    assert saved == {
        "kind": "anomalies",
        "start": date(2026, 1, 1),
        "end": date(2026, 10, 1),
        "seed": 42,
    }
    report = cast(ReportOut, app.session_state["selected_report"])
    assert report.kind == "anomalies"
    assert report.parameters["seed"] == 42
    assert report.result["seed"] == 42
    app.run()
    assert len(api.calls) == 2


def test_invalid_detection_dates_do_not_call_backend(api: MemoryAPI) -> None:
    """A reversed detection interval is rejected before the detector GET."""
    app = open_app()
    date_input(app, "Detection start").set_value(date(2026, 11, 1))
    button(app, "Detect anomalies").click().run()
    assert not app.exception
    assert not api.calls
    assert any("Check detection dates" in item.value for item in app.error)


def test_chat_submits_once_and_keeps_mock_report_evidence_on_rerun(
    api: MemoryAPI,
) -> None:
    """A retained response is presentation state, not another creation request."""
    app = open_app("AI analyst")
    assert not api.calls
    app.chat_input[0].set_value("  Why did revenue change?  ").run()
    assert not app.exception
    assert api.calls == [("create_run", "Why did revenue change?")]
    assert any("no language model was called" in item.value for item in app.info)
    assert any("Facts 1 · evidence" == item.label for item in app.expander)
    assert any("comparison-1" in item.value for item in app.json)
    assert len(app.get("download_button")) == 1
    app.run()
    assert api.calls == [("create_run", "Why did revenue change?")]
    assert len(app.session_state["chat-entries"]) == 1


@pytest.mark.parametrize("question", ["ab", "  ", " a "])
def test_invalid_chat_question_never_calls_backend(
    api: MemoryAPI, question: str
) -> None:
    """Whitespace and too-short inputs are rejected before any POST."""
    app = open_app("AI analyst")
    app.chat_input[0].set_value(question).run()
    assert not app.exception
    assert not api.calls
    assert any("3–2000" in item.value for item in app.error)


def test_safe_chat_failure_stays_readable_across_reruns(api: MemoryAPI) -> None:
    """A network failure becomes a retained public error without a hidden retry."""
    api.errors["create_run"] = APIError(
        "Cannot reach the API. Check that it is running."
    )
    app = open_app("AI analyst")
    app.chat_input[0].set_value("Why did revenue change?").run()
    assert not app.exception
    assert [item.value for item in app.error] == [
        "Cannot reach the API. Check that it is running."
    ]
    app.run()
    assert len(api.calls) == 1
    assert len(app.session_state["chat-entries"]) == 1


def test_handled_chat_failure_opens_stored_trace_without_repeating_post(
    api: MemoryAPI,
) -> None:
    """A returned run id recovers the failed investigation through one GET."""
    api.run_result = investigation(failed=True)
    api.errors["create_run"] = APIError(
        "The agent could not produce a valid report.", 502, api.run_result.id
    )
    app = open_app("AI analyst")
    app.chat_input[0].set_value("Why did revenue change?").run()
    assert not app.exception
    assert api.calls == [
        ("create_run", "Why did revenue change?"),
        ("run", api.run_result.id),
    ]
    assert any("The report was invalid." == item.value for item in app.error)
    assert len(app.get("download_button")) == 1
    app.run()
    assert len(api.calls) == 2


def test_report_history_refresh_open_and_rerun_never_recompute(api: MemoryAPI) -> None:
    """Browsing uses only list/detail GETs and renders the immutable answer."""
    app = open_app("Reports")
    assert not api.calls
    button(app, "Refresh reports").click().run()
    button(app, "Open report").click().run()
    assert not app.exception
    assert api.calls == [("reports", (10, 0)), ("report", UUID(int=200 << 96))]
    assert any(item.value == "9 007 199 254 740 993.00 RUB" for item in app.metric)
    assert len(app.get("download_button")) == 1
    app.run()
    assert len(api.calls) == 2


@pytest.mark.parametrize(
    ("page", "refresh", "next_label", "previous_label", "method", "empty_message"),
    [
        (
            "Reports",
            "Refresh reports",
            "Next reports",
            "Previous reports",
            "reports",
            "No saved reports on this page.",
        ),
        (
            "AI analyst",
            "Refresh investigations",
            "Next investigations",
            "Previous investigations",
            "runs",
            "No investigations on this page.",
        ),
    ],
)
def test_history_pagination_uses_offsets_without_duplicate_fetches(
    api: MemoryAPI,
    page: str,
    refresh: str,
    next_label: str,
    previous_label: str,
    method: str,
    empty_message: str,
) -> None:
    """Each navigation action fetches one page, including its empty last page."""
    app = open_app(page)
    button(app, refresh).click().run()
    assert button(app, previous_label).disabled
    button(app, next_label).click().run()
    assert not app.exception
    assert api.calls == [(method, (10, 0)), (method, (10, 10))]
    assert button(app, next_label).disabled
    assert any(item.value == empty_message for item in app.info)
    button(app, previous_label).click().run()
    assert api.calls == [(method, (10, 0)), (method, (10, 10)), (method, (10, 0))]
    app.run()
    assert len(api.calls) == 3
