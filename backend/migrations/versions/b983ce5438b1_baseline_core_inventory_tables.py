"""baseline core inventory tables

Creates the inventory, consumption, purchase order and forecast override
tables that were previously defined only in the ORM models.

Every creation step is guarded by an existence check, so this revision is
safe on a brand-new database and on an existing database where some of these
tables were already created by hand.

Revision ID: b983ce5438b1
Revises: 0261074d722c
Create Date: 2026-11-23 21:08:04.834188
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b983ce5438b1"
down_revision: Union[str, Sequence[str], None] = "0261074d722c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_indexes(table: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    tables = _existing_tables()

    if "inventory_items" not in tables:
        op.create_table(
            "inventory_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("item_code", sa.String(length=100), nullable=False),
            sa.Column("item_name", sa.String(length=255), nullable=False),
            sa.Column("category", sa.String(length=150), nullable=True),
            sa.Column("unit_of_measure", sa.String(length=30), nullable=False),
            sa.Column("on_hand_quantity", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("reserved_quantity", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("reorder_level", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("safety_stock", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("lead_time_days", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("lead_time_days >= 0", name="ck_inventory_lead_time_nonnegative"),
            sa.CheckConstraint("on_hand_quantity >= 0", name="ck_inventory_on_hand_nonnegative"),
            sa.CheckConstraint("reorder_level >= 0", name="ck_inventory_reorder_nonnegative"),
            sa.CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"),
            sa.CheckConstraint("safety_stock >= 0", name="ck_inventory_safety_nonnegative"),
            sa.CheckConstraint("unit_cost >= 0", name="ck_inventory_unit_cost_nonnegative"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_inventory_item_name", "inventory_items", ["item_name"], unique=False)
        op.create_index("ix_inventory_items_item_code", "inventory_items", ["item_code"], unique=True)

    if "forecast_overrides" not in tables:
        op.create_table(
            "forecast_overrides",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("inventory_item_id", sa.Integer(), nullable=False),
            sa.Column("forecast_start_date", sa.Date(), nullable=False),
            sa.Column("forecast_end_date", sa.Date(), nullable=False),
            sa.Column("original_predicted_demand", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("adjusted_demand", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("adjusted_by", sa.String(length=150), nullable=False),
            sa.Column("reason", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("adjusted_demand >= 0", name="ck_forecast_adjusted_demand_nonnegative"),
            sa.CheckConstraint("forecast_start_date <= forecast_end_date", name="ck_forecast_override_valid_dates"),
            sa.CheckConstraint("original_predicted_demand >= 0", name="ck_forecast_original_demand_nonnegative"),
            sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("inventory_item_id", "forecast_start_date", name="uq_forecast_override_item_period"),
        )
        op.create_index("ix_forecast_overrides_inventory_item_id", "forecast_overrides", ["inventory_item_id"], unique=False)

    if "inventory_consumption" not in tables:
        op.create_table(
            "inventory_consumption",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("inventory_item_id", sa.Integer(), nullable=False),
            sa.Column("consumption_date", sa.Date(), nullable=False),
            sa.Column("quantity_consumed", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("reference", sa.String(length=100), nullable=True),
            sa.Column("notes", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("quantity_consumed > 0", name="ck_consumption_quantity_positive"),
            sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_consumption_item_date", "inventory_consumption", ["inventory_item_id", "consumption_date"], unique=False)
        op.create_index("ix_inventory_consumption_inventory_item_id", "inventory_consumption", ["inventory_item_id"], unique=False)

    if "purchase_orders" not in tables:
        op.create_table(
            "purchase_orders",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("po_number", sa.String(length=100), nullable=False),
            sa.Column("inventory_item_id", sa.Integer(), nullable=False),
            sa.Column("supplier_name", sa.String(length=255), nullable=False),
            sa.Column("ordered_quantity", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("received_quantity", sa.Numeric(precision=14, scale=3), nullable=False),
            sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("order_date", sa.Date(), nullable=False),
            sa.Column("expected_delivery_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("notes", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint(
                "status IN ('draft', 'pending', 'approved', 'ordered', 'partially_received', 'received', 'cancelled')",
                name="ck_po_valid_status",
            ),
            sa.CheckConstraint("ordered_quantity > 0", name="ck_po_ordered_quantity_positive"),
            sa.CheckConstraint("received_quantity <= ordered_quantity", name="ck_po_received_not_above_ordered"),
            sa.CheckConstraint("received_quantity >= 0", name="ck_po_received_quantity_nonnegative"),
            sa.CheckConstraint("unit_cost >= 0", name="ck_po_unit_cost_nonnegative"),
            sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_purchase_order_item_status", "purchase_orders", ["inventory_item_id", "status"], unique=False)
        op.create_index("ix_purchase_orders_inventory_item_id", "purchase_orders", ["inventory_item_id"], unique=False)
        op.create_index("ix_purchase_orders_po_number", "purchase_orders", ["po_number"], unique=True)


def downgrade() -> None:
    # Dropping business tables is destructive. Downgrade is intentionally a no-op;
    # restore from backup if you need to reverse this baseline.
    pass
