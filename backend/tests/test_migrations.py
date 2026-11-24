from alembic import command
from sqlalchemy import inspect

from app.database.connection import engine
from tests.helpers import count_rows


CORE_TABLES = {
    "inventory_items", "inventory_consumption", "purchase_orders", "forecast_overrides",
    "assistant_conversations", "assistant_messages",
}


def test_fresh_database_has_every_table():
    tables = set(inspect(engine).get_table_names())
    assert CORE_TABLES <= tables


def test_reserved_not_above_on_hand_is_enforced_by_database():
    with engine.connect() as conn:
        names = {c["name"] for c in inspect(conn).get_check_constraints("inventory_items")}
    assert "ck_inventory_reserved_not_above_on_hand" in names


def test_assistant_conversation_has_context_columns():
    columns = {c["name"] for c in inspect(engine).get_columns("assistant_conversations")}
    assert {"context_item_id", "summarized_through_id"} <= columns


def test_baseline_is_safe_to_rerun_on_existing_tables(alembic_cfg):
    # Step back to before the business-table baseline. Its downgrade is a no-op,
    # so the tables remain in place. Re-applying it must not fail or duplicate them.
    command.downgrade(alembic_cfg, "0261074d722c")
    command.upgrade(alembic_cfg, "head")
    assert CORE_TABLES <= set(inspect(engine).get_table_names())
    assert count_rows("inventory_items") == 0


def test_migration_head_is_current(alembic_cfg):
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(alembic_cfg).get_current_head()
    assert head == "c4f1a7e9d2b3"
