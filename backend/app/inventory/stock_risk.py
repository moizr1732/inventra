
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import InventoryItem
from app.models.purchase_order import PurchaseOrder
from app.inventory.consumption_analytics import (
    get_consumption_analytics,
)


def get_item_stock_risk(
    db: Session,
    item_id: int,
    days: int = 90,
    overstock_days: int = 60,
):
    if overstock_days < 1:
        raise ValueError("Overstock threshold must be positive.")

    analytics = get_consumption_analytics(
        db=db,
        item_id=item_id,
        days=days,
    )

    if analytics is None:
        return None

    item = db.get(InventoryItem, item_id)

    average_daily = Decimal(
        str(analytics["average_daily_consumption"])
    )

    available_stock = Decimal(
        str(analytics["available_quantity"])
    )

    lead_time = item.lead_time_days
    safety_stock = Decimal(str(item.safety_stock))

    # Count only approved or active purchase orders.
    open_po_total = (
        db.query(
            func.sum(
                PurchaseOrder.ordered_quantity
                - PurchaseOrder.received_quantity
            )
        )
        .filter(
            PurchaseOrder.inventory_item_id == item_id,
            PurchaseOrder.status.in_(
                ["approved", "ordered", "partially_received"]
            ),
        )
        .scalar()
    )

    outstanding_open_po_quantity = Decimal(
        str(open_po_total or 0)
    )

    # Dynamic reorder point based on demand, lead time and safety stock.
    calculated_reorder_point = (
        average_daily * Decimal(lead_time) + safety_stock
    )

    # Inventory position includes stock already on order.
    inventory_position = (
        available_stock + outstanding_open_po_quantity
    )

    days_cover = analytics["days_of_cover"]

    if average_daily == 0:
        risk_level = "no_demand_data"
    elif days_cover <= lead_time:
        risk_level = "critical"
    elif available_stock <= calculated_reorder_point:
        risk_level = "low_stock"
    elif days_cover > overstock_days:
        risk_level = "overstock"
    else:
        risk_level = "normal"

    # Avoid recommending quantities already covered by open POs.
    suggested_order_quantity = max(
        calculated_reorder_point - inventory_position,
        Decimal("0"),
    )

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "risk_level": risk_level,
        "average_daily_consumption": average_daily,
        "available_quantity": available_stock,
        "outstanding_open_po_quantity": outstanding_open_po_quantity,
        "inventory_position": inventory_position,
        "lead_time_days": lead_time,
        "safety_stock": safety_stock,
        "calculated_reorder_point": calculated_reorder_point,
        "days_of_cover": days_cover,
        "overstock_threshold_days": overstock_days,
        "suggested_order_quantity": suggested_order_quantity,
        "requires_replenishment": suggested_order_quantity > 0,
    }
