"""Shared builders for tests. Data is synthetic."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.database.connection import engine
from app.database.session import SessionLocal
from app.forecasting.periods import history_period_starts, period_end_for
from app.models import InventoryConsumption


def make_item(client, code="FAB-001", name="Cotton Fabric", on_hand=100, reserved=0,
              reorder_level=0, safety_stock=0, lead_time_days=0, unit_cost=2, unit="m"):
    response = client.post("/inventory", json={
        "item_code": code,
        "item_name": name,
        "category": "Textiles",
        "unit_of_measure": unit,
        "on_hand_quantity": str(on_hand),
        "reserved_quantity": str(reserved),
        "reorder_level": str(reorder_level),
        "safety_stock": str(safety_stock),
        "lead_time_days": lead_time_days,
        "unit_cost": str(unit_cost),
    })
    assert response.status_code == 201, response.text
    return response.json()


def backdate_item(item_id: int, days: int = 400):
    """Make an item look older than the forecast history window."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE inventory_items SET created_at = :ts WHERE id = :id"),
            {"ts": datetime.now(timezone.utc) - timedelta(days=days), "id": item_id},
        )


def history_window():
    """Start and end dates of the 90-day forecast history window."""
    starts = history_period_starts(date.today())
    return starts[0], period_end_for(starts[-1])


def seed_daily(item_id: int, quantity: float, start: date, end: date):
    """Insert one consumption record per day from start to end inclusive."""
    db = SessionLocal()
    try:
        day = start
        while day <= end:
            db.add(InventoryConsumption(
                inventory_item_id=item_id,
                consumption_date=day,
                quantity_consumed=Decimal(str(quantity)),
            ))
            day += timedelta(days=1)
        db.commit()
    finally:
        db.close()


def seed_history(item_id: int, quantity_per_day: float):
    """Fill the full 90-day forecast history window with a steady daily rate."""
    start, end = history_window()
    seed_daily(item_id, quantity_per_day, start, end)


def seed_analytics_window(item_id: int, quantity_per_day: float):
    """Fill the 90-day stock-risk analytics window ending yesterday."""
    end = date.today() - timedelta(days=1)
    seed_daily(item_id, quantity_per_day, end - timedelta(days=89), end)


def count_rows(table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def get_item_row(item_id: int):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT on_hand_quantity, reserved_quantity FROM inventory_items WHERE id = :id"),
            {"id": item_id},
        ).one()


def seed_continuous(item_id: int, quantity_per_day: float):
    """One continuous daily series from the start of the forecast history window
    up to yesterday. Covers both the 90-day stock-risk window and the
    forecast history, without counting any day twice."""
    history_start, _ = history_window()
    end = date.today() - timedelta(days=1)
    seed_daily(item_id, quantity_per_day, min(history_start, end - timedelta(days=89)), end)
