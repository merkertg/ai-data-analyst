"""Add API tokens: name, role, SHA-256 hash, expiry and revocation.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22 10:00:00.000000

Этап 09: доступ к /api только по токену. Таблица хранит хэш токена,
а не сам токен; CHECK-ограничения проверяют роль, формат хэша и срок.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создать таблицу токенов с уникальным хэшем."""
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=12), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name=op.f("ck_api_tokens_expires_after_creation"),
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0", name=op.f("ck_api_tokens_name_not_blank")
        ),
        sa.CheckConstraint(
            "role IN ('viewer', 'analyst')", name=op.f("ck_api_tokens_role_allowed")
        ),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_api_tokens_hash_is_sha256")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_tokens_token_hash")),
    )


def downgrade() -> None:
    """Удалить таблицу токенов: все выданные токены перестанут работать."""
    op.drop_table("api_tokens")
