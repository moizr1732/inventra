from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.inventory.consumption_analytics import get_consumption_analytics
from app.inventory.policy import (
    ZERO,
    calculate_suggested_order,
    classify_risk,
    quantize_qty,
)
from app.models import InventoryItem
from app.models.purchase_order import PurchaseOrder

OPEN_PO_STATUSES = ("approved", "ordered", "partially_received")


def get_open_po_quantity(db: Session, item_id: int) -> Decimal:
    total = (
        db.query(
            func.sum(PurchaseOrder.ordered_quantity - PurchaseOrder.received_quantity)
        )
        .filter(
            PurchaseOrder.inventory_item_id == item_id,
            PurchaseOrder.status.in_(OPEN_PO_STATUSES),
        )
        .scalar()
    )
    return quantize_qty(Decimal(str(total or 0)))


def get_item_stock_risk(
    db: Session,
    item_id: int,
    days: int = 90,
    overstock_days: int = 60,
):
    if overstock_days < 1:
        raise ValueError("Overstock threshold must be positive.")

    analytics = get_consumption_analytics(db=db, item_id=item_id, days=days)
    if analytics is None:
        return None

    item = db.get(InventoryItem, item_id)

    average_daily = analytics["average_daily_consumption"]
    available = analytics["available_quantity"]
    days_cover = analytics["days_of_cover"]
    reorder_point = analytics["reorder_point"]
    outstanding_po = get_open_po_quantity(db, item_id)
    inventory_position = quantize_qty(available + outstanding_po)

    risk_level = classify_risk(
        average_daily=average_daily,
        available=available,
        days_of_cover=days_cover,
        lead_time_days=item.lead_time_days,
        reorder_point=reorder_point,
        overstock_days=overstock_days,
    )

    suggested = calculate_suggested_order(reorder_point, inventory_position)

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "unit_of_measure": item.unit_of_measure,
        "risk_level": risk_level,
        "average_daily_consumption": average_daily,
        "observed_days": analytics["observed_days"],
        "available_quantity": available,
        "outstanding_open_po_quantity": outstanding_po,
        "inventory_position": inventory_position,
        "lead_time_days": item.lead_time_days,
        "safety_stock": Decimal(str(item.safety_stock)),
        "reorder_level": Decimal(str(item.reorder_level)),
        "calculated_reorder_point": reorder_point,
        "days_of_cover": days_cover,
        "overstock_threshold_days": overstock_days,
        "suggested_order_quantity": suggested,
        "requires_replenishment": suggested > ZERO,
    }
