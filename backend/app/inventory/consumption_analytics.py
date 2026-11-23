
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import InventoryItem, InventoryConsumption


def get_consumption_analytics(
    db: Session,
    item_id: int,
    days: int = 90,
):
    if days < 1 or days > 365:
        raise ValueError("Days must be between 1 and 365.")

    item = db.get(InventoryItem, item_id)

    if item is None or not item.is_active:
        return None

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)

    result = db.execute(
        select(
            func.count(InventoryConsumption.id),
            func.coalesce(
                func.sum(InventoryConsumption.quantity_consumed),
                0,
            ),
        ).where(
            InventoryConsumption.inventory_item_id == item_id,
            InventoryConsumption.consumption_date >= start_date,
            InventoryConsumption.consumption_date <= end_date,
        )
    ).one()

    record_count = result[0]
    total_consumption = Decimal(str(result[1]))

    average_daily = total_consumption / Decimal(days)

    available_stock = item.available_quantity

    if average_daily > 0:
        days_of_cover = available_stock / average_daily
    else:
        days_of_cover = None

    reorder_point = item.reorder_level

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "period_days": days,
        "start_date": start_date,
        "end_date": end_date,
        "records_count": record_count,
        "total_consumption": total_consumption,
        "average_daily_consumption": average_daily,
        "on_hand_quantity": item.on_hand_quantity,
        "reserved_quantity": item.reserved_quantity,
        "available_quantity": available_stock,
        "days_of_cover": days_of_cover,
        "reorder_point": reorder_point,
        "below_reorder_point": available_stock <= reorder_point,
    }
