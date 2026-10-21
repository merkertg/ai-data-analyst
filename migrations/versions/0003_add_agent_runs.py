"""Add agent runs: question, report or error and tool trace.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21 13:38:56.199480

Создана alembic revision --autogenerate и проверена вручную: одна таблица
agent_runs без связей с таблицами продаж. CHECK-ограничения требуют, чтобы
успешный запуск хранил отчёт, а неудачный — ошибку.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создать таблицу истории запусков агента и индекс по времени."""
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trace", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("app_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND report IS NOT NULL AND error IS NULL)"
            " OR (status = 'failed' AND report IS NULL AND error IS NOT NULL)",
            name=op.f("ck_agent_runs_outcome_matches_status"),
        ),
        sa.CheckConstraint(
            "provider IN ('mock', 'openai')",
            name=op.f("ck_agent_runs_provider_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'failed')",
            name=op.f("ck_agent_runs_status_allowed"),
        ),
        sa.CheckConstraint(
            "duration_ms >= 0", name=op.f("ck_agent_runs_duration_not_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index(
        op.f("ix_agent_runs_created_at"), "agent_runs", ["created_at"], unique=False
    )


def downgrade() -> None:
    """Удалить таблицу запусков — вместе со всей историей расследований."""
    op.drop_index(op.f("ix_agent_runs_created_at"), table_name="agent_runs")
    op.drop_table("agent_runs")
