from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.inventory.policy import (
    ZERO,
    calculate_days_of_cover,
    calculate_reorder_point,
    quantize_qty,
)
from app.models import InventoryConsumption, InventoryItem


def get_consumption_analytics(db: Session, item_id: int, days: int = 90):
    """Consumption statistics for an active item over the last `days` days.

    Average daily demand is measured over the days the item has actually been
    tracked inside the window, not the full window length. Dividing by the
    full window would make a new item look like it has very low demand.
    """
    if days < 1 or days > 365:
        raise ValueError("Days must be between 1 and 365.")

    item = db.get(InventoryItem, item_id)
    if item is None or not item.is_active:
        return None

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)

    total, count, first_date = db.execute(
        select(
            func.coalesce(func.sum(InventoryConsumption.quantity_consumed), 0),
            func.count(InventoryConsumption.id),
            func.min(InventoryConsumption.consumption_date),
        ).where(
            InventoryConsumption.inventory_item_id == item_id,
            InventoryConsumption.consumption_date >= start_date,
            InventoryConsumption.consumption_date <= end_date,
        )
    ).one()

    total_consumption = Decimal(str(total))

    if count == 0 or first_date is None:
        observed_days = 0
        average_daily = ZERO
    else:
        observed_start = max(start_date, first_date)
        observed_days = (end_date - observed_start).days + 1
        average_daily = quantize_qty(total_consumption / Decimal(observed_days))

    available = item.available_quantity
    days_of_cover = calculate_days_of_cover(available, average_daily)
    reorder_point = calculate_reorder_point(
        average_daily,
        item.lead_time_days,
        Decimal(str(item.safety_stock)),
        Decimal(str(item.reorder_level)),
    )

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "period_days": days,
        "start_date": start_date,
        "end_date": end_date,
        "records_count": count,
        "total_consumption": total_consumption,
        "observed_days": observed_days,
        "average_daily_consumption": average_daily,
        "on_hand_quantity": item.on_hand_quantity,
        "reserved_quantity": item.reserved_quantity,
        "available_quantity": available,
        "days_of_cover": days_of_cover,
        "reorder_point": reorder_point,
        "below_reorder_point": available <= reorder_point,
    }
