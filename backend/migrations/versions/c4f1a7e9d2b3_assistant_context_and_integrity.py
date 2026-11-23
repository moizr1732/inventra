"""assistant conversation context and inventory integrity constraint

- assistant_conversations.context_item_id: the inventory item the conversation
  is currently discussing (stores only an ID; facts are always re-read live).
- assistant_conversations.summarized_through_id: watermark for incremental
  conversation summarisation.
- ck_inventory_reserved_not_above_on_hand: database-level guarantee that
  reserved stock never exceeds on-hand stock.

Idempotent: each change is skipped if already present. The constraint step
aborts with a clear message if existing data would violate it.

Revision ID: c4f1a7e9d2b3
Revises: b983ce5438b1
Create Date: 2026-11-24 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f1a7e9d2b3"
down_revision: Union[str, Sequence[str], None] = "b983ce5438b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _check_names(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    conv_cols = _columns("assistant_conversations")

    if "context_item_id" not in conv_cols:
        op.add_column(
            "assistant_conversations",
            sa.Column("context_item_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_assistant_conversations_context_item",
            "assistant_conversations",
            "inventory_items",
            ["context_item_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if "summarized_through_id" not in conv_cols:
        op.add_column(
            "assistant_conversations",
            sa.Column("summarized_through_id", sa.Integer(), nullable=True),
        )

    if "ck_inventory_reserved_not_above_on_hand" not in _check_names("inventory_items"):
        bind = op.get_bind()
        bad = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM inventory_items "
                "WHERE reserved_quantity > on_hand_quantity"
            )
        ).scalar()
        if bad:
            raise RuntimeError(
                f"Cannot add ck_inventory_reserved_not_above_on_hand: "
                f"{bad} item(s) have reserved_quantity above on_hand_quantity. "
                "Correct those records and re-run the migration."
            )
        op.create_check_constraint(
            "ck_inventory_reserved_not_above_on_hand",
            "inventory_items",
            "reserved_quantity <= on_hand_quantity",
        )


def downgrade() -> None:
    if "ck_inventory_reserved_not_above_on_hand" in _check_names("inventory_items"):
        op.drop_constraint(
            "ck_inventory_reserved_not_above_on_hand", "inventory_items", type_="check"
        )
    if "summarized_through_id" in _columns("assistant_conversations"):
        op.drop_column("assistant_conversations", "summarized_through_id")
    if "context_item_id" in _columns("assistant_conversations"):
        op.drop_constraint(
            "fk_assistant_conversations_context_item",
            "assistant_conversations",
            type_="foreignkey",
        )
        op.drop_column("assistant_conversations", "context_item_id")
