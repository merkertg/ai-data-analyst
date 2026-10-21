"""Local Streamlit interface: dashboard, independent questions and snapshots."""

from collections.abc import Sequence
from datetime import date
from typing import cast
from uuid import UUID

import streamlit as st
from pydantic import ValidationError

from app.agents.schemas import Fact, Hypothesis
from app.analytics.models import Dimension
from app.schemas.agents import AgentQuestion, AgentRunList, AgentRunOut
from app.schemas.analytics import (
    AnomalyQuery,
    AnomalyReportResponse,
    ComparisonQuery,
    ContributionsResponse,
)
from app.schemas.reports import (
    AnomalyReportRequest,
    ComparisonReportRequest,
    ReportList,
    ReportOut,
)
from ui.charts import (
    contribution_chart,
    money,
    orders_chart,
    percentage,
    revenue_chart,
)
from ui.client import APIClient, APIError
from ui.config import UISettings
from ui.models import ChatEntry, DashboardSnapshot

PAGE_SIZE = 10


def show_error(error: APIError) -> None:
    """Display only the client's public message and validated history id."""
    st.error(error.message)
    if error.run_id is not None:
        st.caption(f"Stored failed investigation: {error.run_id}")


def show_contributions(result: ContributionsResponse, key: str) -> None:
    """Present exact metrics beside signed chart coordinates from the API."""
    st.plotly_chart(contribution_chart(result), key=key, width="stretch")
    st.dataframe(
        [
            {
                "Group": item.name,
                "Previous net, RUB": money(item.previous_net),
                "Current net, RUB": money(item.current_net),
                "Change, RUB": money(item.delta),
                "Contribution": percentage(item.contribution_percent),
            }
            for item in result.contributions
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Contributions keep their signs and may exceed 100%. "
        "They describe the arithmetic change, not its cause."
    )


def show_anomalies(result: AnomalyReportResponse) -> None:
    """List candidate signals with the original evidence precision."""
    st.metric("Anomaly candidates", result.finding_count)
    st.caption("Candidates need investigation; they do not prove a cause.")
    if not result.findings:
        st.info("No candidates for this period and detector configuration.")
        return
    st.dataframe(
        [
            {
                "Method": item.method,
                "Metric": item.metric,
                "Entity": ", ".join(f"{k}: {v}" for k, v in item.entity.items()),
                "Start": str(item.period.start),
                "End (exclusive)": str(item.period.end),
                "Observed": str(item.observed),
                "Baseline": "—" if item.baseline is None else str(item.baseline),
                "Score": "—" if item.score is None else str(item.score),
            }
            for item in result.findings
        ],
        hide_index=True,
        width="stretch",
    )


def show_saved_report(report: ReportOut, key: str) -> None:
    """Render and export the returned immutable snapshot, not current filters."""
    st.subheader("Saved snapshot")
    st.caption(f"{report.id} · {report.created_at.isoformat()} · {report.kind}")
    try:
        if report.kind == "comparison":
            result = ContributionsResponse.model_validate(report.result)
            st.metric("Net revenue", money(result.current.net_revenue))
            show_contributions(result, key + "-chart")
        else:
            show_anomalies(AnomalyReportResponse.model_validate(report.result))
    except ValidationError:
        st.error("The saved result does not match the expected report schema.")
    with st.expander("Saved parameters"):
        st.json(report.parameters)
    st.download_button(
        "Download saved report JSON",
        report.model_dump_json(indent=2),
        file_name=f"report-{report.id}.json",
        mime="application/json",
        key=key + "-download",
        on_click="ignore",
    )


def dashboard(client: APIClient) -> None:
    """Load explicit period snapshots; save only from their submitted filters."""
    st.title("Sales, explained.")
    st.caption("INDUSTRIALFLOW · fictional industrial equipment sales")
    st.subheader("Dashboard")
    st.caption(
        "Editable demo preset: September 2026 against August. "
        "Dates use Europe/Moscow; each end date is exclusive."
    )
    with st.form("dashboard-filters"):
        left, right = st.columns(2)
        with left:
            start = st.date_input("Start", date(2026, 9, 1))
            end = st.date_input("End (exclusive)", date(2026, 10, 1))
        with right:
            previous_start = st.date_input("Comparison start", date(2026, 8, 1))
            previous_end = st.date_input("Comparison end (exclusive)", date(2026, 9, 1))
        dimension = cast(Dimension, st.selectbox("Group by", ["category", "region"]))
        submitted = st.form_submit_button("Load dashboard", type="primary")
    if submitted:
        st.session_state.pop("dashboard", None)
        try:
            query = ComparisonQuery(
                start=start,
                end=end,
                compare_start=previous_start,
                compare_end=previous_end,
            )
            with st.spinner("Loading exact metrics…"):
                candidate = DashboardSnapshot(
                    query,
                    dimension,
                    client.revenue(query),
                    client.orders(query),
                    client.contributions(query, dimension),
                )
            st.session_state["dashboard"] = candidate
        except ValidationError:
            st.error("Check both date ranges: start < end, at most 120 months.")
        except APIError as error:
            show_error(error)
    snapshot = st.session_state.get("dashboard")
    if isinstance(snapshot, DashboardSnapshot):
        st.caption(
            f"Loaded: {snapshot.query.start} → {snapshot.query.end} (exclusive); "
            f"comparison {snapshot.query.compare_start} → "
            f"{snapshot.query.compare_end}. These HTTP requests use separate snapshots."
        )
        columns = st.columns(3)
        columns[0].metric("Paid sales", money(snapshot.revenue.paid_sales))
        columns[1].metric("Refunds", money(snapshot.revenue.refunds))
        comparison = snapshot.revenue.comparison
        columns[2].metric(
            "Net revenue",
            money(snapshot.revenue.net_revenue),
            delta=None
            if comparison is None
            else percentage(comparison.net_revenue.percent),
        )
        columns = st.columns(2)
        columns[0].metric("Paid orders", f"{snapshot.orders.paid_orders:,}")
        columns[1].metric(
            "Average order value", money(snapshot.orders.average_order_value)
        )
        left, right = st.columns(2)
        left.plotly_chart(revenue_chart(snapshot.revenue), width="stretch")
        right.plotly_chart(orders_chart(snapshot.orders), width="stretch")
        show_contributions(snapshot.contributions, "dashboard-contributions")
        st.caption(
            "Save recomputes a report from the loaded parameters. "
            "If the database changes, the saved values may differ."
        )
        if st.button("Save comparison report"):
            try:
                request = ComparisonReportRequest(
                    **snapshot.query.model_dump(),
                    kind="comparison",
                    dimension=snapshot.dimension,
                )
                st.session_state["selected_report"] = client.create_report(request)
                st.success("The recomputed snapshot was saved.")
            except APIError as error:
                show_error(error)
    st.divider()
    st.subheader("Anomaly candidates")
    with st.form("anomaly-filters"):
        left, right = st.columns(2)
        anomaly_start = left.date_input("Detection start", date(2026, 1, 1))
        anomaly_end = right.date_input("Detection end (exclusive)", date(2026, 10, 1))
        seed = st.number_input(
            "Detector seed", min_value=0, max_value=2**32 - 1, value=42
        )
        detect = st.form_submit_button("Detect anomalies")
    if detect:
        st.session_state.pop("anomalies", None)
        try:
            anomaly_query = AnomalyQuery(
                start=anomaly_start, end=anomaly_end, seed=int(seed)
            )
            with st.spinner("Detecting candidates…"):
                result = client.anomalies(anomaly_query)
            st.session_state["anomalies"] = (anomaly_query, result)
        except ValidationError:
            st.error("Check detection dates: start < end, at most 120 months.")
        except APIError as error:
            show_error(error)
    saved_anomalies = st.session_state.get("anomalies")
    if saved_anomalies is not None:
        anomaly_query, result = saved_anomalies
        st.caption(f"Loaded: {anomaly_query.start} → {anomaly_query.end} (exclusive).")
        show_anomalies(result)
        if st.button("Save anomaly report"):
            try:
                st.session_state["selected_report"] = client.create_report(
                    AnomalyReportRequest(**anomaly_query.model_dump(), kind="anomalies")
                )
                st.success("The recomputed anomaly snapshot was saved.")
            except APIError as error:
                show_error(error)
    selected = st.session_state.get("selected_report")
    if isinstance(selected, ReportOut):
        st.divider()
        show_saved_report(selected, "dashboard-saved")


def show_run(run: AgentRunOut, key: str) -> None:
    """Separate narrative parts from exact evidence and processed tool traces."""
    st.caption(
        f"{run.status} · {run.provider} / {run.model} · "
        f"{run.steps} steps · {len(run.tool_calls)} calls · {run.duration_ms} ms"
    )
    if run.provider == "mock":
        st.info("Demo provider: real analytics tools; no language model was called.")
    if run.error is not None:
        st.error(run.error.detail)
    report = run.report
    if report is not None:
        st.write(report.summary)
        sections: list[tuple[str, Sequence[Fact | Hypothesis]]] = [
            ("Facts", report.facts),
            ("Hypotheses", report.hypotheses),
        ]
        for label, parts in sections:
            st.markdown(f"#### {label}")
            for index, part in enumerate(parts, 1):
                st.write(f"{index}. {part.statement}")
                with st.expander(f"{label} {index} · evidence"):
                    st.json([item.model_dump() for item in part.evidence])
        for label, lines in (
            ("Recommendations", report.recommendations),
            ("Limitations", report.limitations),
        ):
            st.markdown(f"#### {label}")
            for line in lines:
                st.write("• " + line)
    with st.expander("Processed tool calls and token usage"):
        st.json(
            {
                "tool_calls": [item.model_dump() for item in run.tool_calls],
                "usage": None if run.usage is None else run.usage.model_dump(),
            }
        )
    st.download_button(
        "Download investigation JSON",
        run.model_dump_json(indent=2),
        file_name=f"investigation-{run.id}.json",
        mime="application/json",
        key=key + "-download",
        on_click="ignore",
    )


def investigation_history(client: APIClient) -> None:
    """Load history pages on demand; selecting a row never starts a new run."""
    st.subheader("Investigation history")
    offset = int(st.session_state.get("run-offset", 0))
    if st.button("Refresh investigations"):
        try:
            st.session_state["run-list"] = client.runs(PAGE_SIZE, offset)
        except APIError as error:
            show_error(error)
    result = st.session_state.get("run-list")
    if isinstance(result, AgentRunList):
        left, right = st.columns(2)
        back = left.button("Previous investigations", disabled=result.offset == 0)
        forward = right.button(
            "Next investigations", disabled=len(result.items) < PAGE_SIZE
        )
        if back or forward:
            target = max(0, result.offset + (-PAGE_SIZE if back else PAGE_SIZE))
            try:
                st.session_state["run-list"] = client.runs(PAGE_SIZE, target)
                st.session_state["run-offset"] = target
                st.rerun()
            except APIError as error:
                show_error(error)
        if result.items:
            options = {str(item.id): item for item in result.items}
            run_id = st.selectbox(
                "Stored investigation",
                list(options),
                format_func=lambda value: (
                    f"{options[value].status} · {options[value].question[:70]} "
                    f"· {value[:8]}"
                ),
            )
            if st.button("Open investigation"):
                try:
                    st.session_state["selected_run"] = client.run(UUID(run_id))
                except APIError as error:
                    show_error(error)
        else:
            st.info("No investigations on this page.")
    selected = st.session_state.get("selected_run")
    if isinstance(selected, AgentRunOut):
        st.write(selected.question)
        show_run(selected, "history-" + str(selected.id))


def analyst(client: APIClient) -> None:
    """Send one POST per explicit question and retain responses across reruns."""
    st.title("AI analyst")
    st.caption(
        "Each question starts an independent investigation. Earlier chat messages "
        "are not sent as context. The API selects the provider."
    )
    if "chat-entries" not in st.session_state:
        st.session_state["chat-entries"] = []
    entries: list[ChatEntry] = st.session_state["chat-entries"]
    question = st.chat_input("Ask about sales, returns or stock…", max_chars=2000)
    if question:
        try:
            checked = AgentQuestion(question=question)
            with st.spinner("Investigating with analytics tools…"):
                run = client.create_run(checked.question)
            entries.append(ChatEntry(checked.question, run))
        except ValidationError:
            st.error("Use a question of 3–2000 characters.")
        except APIError as error:
            failed = None
            if error.run_id is not None:
                try:
                    failed = client.run(error.run_id)
                except APIError:
                    pass
            entries.append(ChatEntry(question, failed, error.message))
        # Bound browser-session memory; the API retains the durable history.
        del entries[:-20]
    for index, entry in enumerate(entries):
        with st.chat_message("user"):
            st.write(entry.question)
        with st.chat_message("assistant"):
            if entry.error is not None:
                st.error(entry.error)
            if entry.run is not None:
                show_run(entry.run, f"chat-{index}-{entry.run.id}")
    st.divider()
    investigation_history(client)


def reports(client: APIClient) -> None:
    """Browse immutable saved reports without recomputing their results."""
    st.title("Reports")
    st.caption("Open a stored snapshot. New snapshots are saved from Dashboard.")
    offset = int(st.session_state.get("report-offset", 0))
    if st.button("Refresh reports", type="primary"):
        try:
            st.session_state["report-list"] = client.reports(PAGE_SIZE, offset)
        except APIError as error:
            show_error(error)
    result = st.session_state.get("report-list")
    if isinstance(result, ReportList):
        left, right = st.columns(2)
        back = left.button("Previous reports", disabled=result.offset == 0)
        forward = right.button("Next reports", disabled=len(result.items) < PAGE_SIZE)
        if back or forward:
            target = max(0, result.offset + (-PAGE_SIZE if back else PAGE_SIZE))
            try:
                st.session_state["report-list"] = client.reports(PAGE_SIZE, target)
                st.session_state["report-offset"] = target
                st.rerun()
            except APIError as error:
                show_error(error)
        if result.items:
            options = {str(item.id): item for item in result.items}
            report_id = st.selectbox(
                "Saved report",
                list(options),
                format_func=lambda value: (
                    f"{options[value].kind} · "
                    f"{options[value].created_at:%Y-%m-%d %H:%M} "
                    f"· {value[:8]}"
                ),
            )
            if st.button("Open report"):
                try:
                    st.session_state["selected_report"] = client.report(UUID(report_id))
                except APIError as error:
                    show_error(error)
        else:
            st.info("No saved reports on this page.")
    selected = st.session_state.get("selected_report")
    if isinstance(selected, ReportOut):
        show_saved_report(selected, "report-history")


def main() -> None:
    """Configure a local UI and run only the selected page."""
    st.set_page_config(page_title="IndustrialFlow · AI Data Analyst", layout="wide")
    try:
        settings = UISettings()
    except ValidationError:
        st.error("Check UI_API_URL and UI_REQUEST_TIMEOUT_SECONDS in the environment.")
        st.stop()
    client = APIClient(settings)
    with st.sidebar:
        st.markdown("### IndustrialFlow")
        st.caption("AI DATA ANALYST")
        page = st.radio("Workspace", ["Dashboard", "AI analyst", "Reports"])
        with st.expander("API connection"):
            st.caption(settings.api_url)
            if st.button("Check API"):
                try:
                    ready = client.ready()
                    st.success(f"API ready · schema {ready.get('revision', 'unknown')}")
                except APIError as error:
                    show_error(error)
        st.caption("Fictional data · exact SQL / Decimal analytics")
    if page == "Dashboard":
        dashboard(client)
    elif page == "AI analyst":
        analyst(client)
    else:
        reports(client)


if __name__ == "__main__":
    main()
