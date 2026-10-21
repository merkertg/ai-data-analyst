"""Plot API results without recalculating business metrics in the interface."""

from decimal import Decimal

import plotly.graph_objects as go

from app.schemas.analytics import (
    ContributionsResponse,
    OrdersResponse,
    RevenueResponse,
)


def money(value: Decimal | None) -> str:
    """Format exact API money; an undefined value is not zero."""
    return "—" if value is None else f"{value:,.2f} RUB".replace(",", " ")


def percentage(value: Decimal | None) -> str:
    """Keep undefined percentages distinct from zero and preserve their sign."""
    return "—" if value is None else f"{value:.2f}%"


def revenue_chart(response: RevenueResponse) -> go.Figure:
    """Use floats only for drawing; hover labels retain exact Decimal text."""
    figure = go.Figure()
    for field, label, color in (
        ("paid_sales", "Paid sales", "#94a3b8"),
        ("refunds", "Refunds", "#e19a41"),
        ("net_revenue", "Net revenue", "#0f766e"),
    ):
        amounts = [getattr(point, field) for point in response.monthly]
        figure.add_trace(
            go.Scatter(
                x=[point.period.start.isoformat() for point in response.monthly],
                y=[float(value) for value in amounts],
                customdata=[money(value) for value in amounts],
                mode="lines+markers",
                name=label,
                line={"color": color, "width": 3},
                hovertemplate="%{x}<br>%{customdata}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(
        title="Monthly revenue",
        # A single date point would otherwise produce millisecond tick labels.
        xaxis={"type": "category", "title": "Month bucket (start)"},
        yaxis_title="RUB",
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 20, "r": 20, "t": 55, "b": 55},
        height=340,
    )
    return figure


def orders_chart(response: OrdersResponse) -> go.Figure:
    """Show API order counts without deriving them from revenue or AOV."""
    figure = go.Figure(
        go.Bar(
            x=[point.period.start.isoformat() for point in response.monthly],
            y=[point.paid_orders for point in response.monthly],
            marker_color="#405b85",
            hovertemplate="%{x}<br>%{y} paid orders<extra></extra>",
        )
    )
    figure.update_layout(
        title="Monthly paid orders",
        xaxis={"type": "category", "title": "Month bucket (start)"},
        yaxis_title="Orders",
        margin={"l": 20, "r": 20, "t": 55, "b": 55},
        height=340,
    )
    return figure


def contribution_chart(response: ContributionsResponse) -> go.Figure:
    """Keep signed deltas and shares, including negative or over-100% shares."""
    items = list(reversed(response.contributions))
    figure = go.Figure(
        go.Bar(
            x=[float(item.delta) for item in items],
            y=[item.name for item in items],
            orientation="h",
            customdata=[
                [money(item.delta), percentage(item.contribution_percent)]
                for item in items
            ],
            marker_color=["#bd5450" if item.delta < 0 else "#0f766e" for item in items],
            hovertemplate=(
                "%{y}<br>Change: %{customdata[0]}"
                "<br>Contribution: %{customdata[1]}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title=f"Net revenue change by {response.dimension}",
        xaxis_title="Change, RUB",
        margin={"l": 20, "r": 20, "t": 55, "b": 30},
        height=max(300, 45 * len(items)),
    )
    return figure
