"""Single source of truth for reorder and risk rules.

Pure functions only: no database access, so they are easy to test and the
stock-risk engine, consumption analytics and the assistant all agree.

Definitions
-----------
* Reorder point (ROP) = average daily demand x lead time + safety stock,
  never lower than the item's manually configured reorder level.
* Inventory position = available stock + open purchase-order quantity.
* Suggested order = amount needed to bring inventory position back up to the
  reorder point (zero if already covered).
* Risk level is based on physical available stock, so an inbound order that
  has not yet arrived does not hide a current shortage.
"""
from decimal import Decimal

ZERO = Decimal("0")
QTY_PLACES = Decimal("0.001")

RISK_RANK = {
    "critical": 0,
    "low_stock": 1,
    "no_demand_data": 2,
    "normal": 3,
    "overstock": 4,
}


def quantize_qty(value: Decimal) -> Decimal:
    return value.quantize(QTY_PLACES)


def calculate_reorder_point(
    average_daily: Decimal,
    lead_time_days: int,
    safety_stock: Decimal,
    reorder_level: Decimal,
) -> Decimal:
    demand_during_lead_time = average_daily * Decimal(lead_time_days)
    calculated = demand_during_lead_time + safety_stock
    return quantize_qty(max(calculated, reorder_level))


def calculate_days_of_cover(available: Decimal, average_daily: Decimal) -> Decimal | None:
    if average_daily <= ZERO:
        return None
    return quantize_qty(available / average_daily)


def classify_risk(
    average_daily: Decimal,
    available: Decimal,
    days_of_cover: Decimal | None,
    lead_time_days: int,
    reorder_point: Decimal,
    overstock_days: int,
) -> str:
    if average_daily <= ZERO or days_of_cover is None:
        return "no_demand_data"
    if available <= ZERO or days_of_cover <= Decimal(lead_time_days):
        return "critical"
    if available <= reorder_point:
        return "low_stock"
    if days_of_cover > Decimal(overstock_days):
        return "overstock"
    return "normal"


def calculate_suggested_order(reorder_point: Decimal, inventory_position: Decimal) -> Decimal:
    return quantize_qty(max(reorder_point - inventory_position, ZERO))
