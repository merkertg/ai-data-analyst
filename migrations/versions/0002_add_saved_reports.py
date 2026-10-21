"""Add saved reports: parameters, exact JSON result, app version and time.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21 12:59:59.488636

Создана alembic revision --autogenerate и проверена вручную: добавляется
одна таблица reports без связей с таблицами продаж — отчёт хранит снимок
результата, а не ссылки на строки, которые могут измениться позже.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создать таблицу сохранённых отчётов и индекс по времени создания."""
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column(
            "parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("app_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('comparison', 'anomalies')", name=op.f("ck_reports_kind_allowed")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(
        op.f("ix_reports_created_at"), "reports", ["created_at"], unique=False
    )


def downgrade() -> None:
    """Удалить таблицу отчётов — вместе со всеми сохранёнными отчётами."""
    op.drop_index(op.f("ix_reports_created_at"), table_name="reports")
    op.drop_table("reports")
