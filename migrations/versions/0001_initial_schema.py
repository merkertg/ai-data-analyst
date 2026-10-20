"""Initial schema: customers, products, orders, items, refunds, inventory.

Revision ID: 0001
Revises: (none - first migration)
Create Date: 2026-10-20 16:02:09.875100

Создана командой alembic revision --autogenerate и проверена вручную:
порядок таблиц учитывает внешние ключи (сначала родители), имена ограничений
заданы соглашением из app/db/base.py, downgrade удаляет всё в обратном порядке.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создать шесть таблиц с ключами, проверками и индексами."""
    # Справочники: клиенты и товары ни от кого не зависят.
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=False),
        sa.Column("industry", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "length(trim(industry)) > 0", name=op.f("ck_customers_industry_not_blank")
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_customers_name_not_blank")
        ),
        sa.CheckConstraint(
            "length(trim(region)) > 0", name=op.f("ck_customers_region_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index(op.f("ix_customers_region"), "customers", ["region"], unique=False)
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("cost >= 0", name=op.f("ck_products_cost_not_negative")),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_products_name_not_blank")
        ),
        sa.CheckConstraint(
            "length(trim(sku)) > 0", name=op.f("ck_products_sku_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("sku", name=op.f("uq_products_sku")),
    )
    op.create_index(
        op.f("ix_products_category"), "products", ["category"], unique=False
    )
    # Остатки и заказы ссылаются на товары и клиентов.
    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0", name=op.f("ck_inventory_snapshots_quantity_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_inventory_snapshots_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_snapshots")),
        sa.UniqueConstraint(
            "product_id",
            "snapshot_date",
            name=op.f("uq_inventory_snapshots_product_id_snapshot_date"),
        ),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default="pending", nullable=False
        ),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'paid') = (paid_at IS NOT NULL)",
            name=op.f("ck_orders_paid_at_matches_status"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled')",
            name=op.f("ck_orders_status_allowed"),
        ),
        sa.CheckConstraint(
            "paid_at >= ordered_at", name=op.f("ck_orders_paid_after_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_orders_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index(
        op.f("ix_orders_customer_id"), "orders", ["customer_id"], unique=False
    )
    op.create_index(op.f("ix_orders_paid_at"), "orders", ["paid_at"], unique=False)
    # Позиции ссылаются на заказ и товар, возвраты - на позицию.
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "discount",
            sa.Numeric(precision=5, scale=4),
            server_default="0",
            nullable=False,
        ),
        sa.CheckConstraint(
            "discount >= 0 AND discount < 1", name=op.f("ck_order_items_discount_range")
        ),
        sa.CheckConstraint(
            "quantity > 0", name=op.f("ck_order_items_quantity_positive")
        ),
        sa.CheckConstraint(
            "unit_price >= 0", name=op.f("ck_order_items_unit_price_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_order_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.UniqueConstraint(
            "order_id", "product_id", name=op.f("uq_order_items_order_id_product_id")
        ),
    )
    op.create_index(
        op.f("ix_order_items_product_id"), "order_items", ["product_id"], unique=False
    )
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name=op.f("ck_refunds_amount_positive")),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("fk_refunds_order_item_id_order_items"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refunds")),
    )
    op.create_index(
        op.f("ix_refunds_order_item_id"), "refunds", ["order_item_id"], unique=False
    )
    op.create_index(
        op.f("ix_refunds_processed_at"), "refunds", ["processed_at"], unique=False
    )


def downgrade() -> None:
    """Удалить все таблицы этапа 02 - вместе с данными в них."""
    # Обратный порядок: сначала зависимые таблицы, затем справочники.
    op.drop_index(op.f("ix_refunds_processed_at"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_order_item_id"), table_name="refunds")
    op.drop_table("refunds")
    op.drop_index(op.f("ix_order_items_product_id"), table_name="order_items")
    op.drop_table("order_items")
    op.drop_index(op.f("ix_orders_paid_at"), table_name="orders")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_table("orders")
    op.drop_table("inventory_snapshots")
    op.drop_index(op.f("ix_products_category"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_customers_region"), table_name="customers")
    op.drop_table("customers")
