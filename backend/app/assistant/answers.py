"""Answer builders. Every figure shown to the user comes from PostgreSQL via
the existing domain services. Nothing here is remembered from conversation
history and nothing is invented: when data is missing the text says so."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.forecasting.demand_forecast import generate_three_month_forecast
from app.forecasting.planning_demand import get_planning_demand
from app.inventory.policy import RISK_RANK, calculate_reorder_point, classify_risk, calculate_days_of_cover, calculate_suggested_order, quantize_qty
from app.inventory.stock_risk import get_item_stock_risk
from app.models import InventoryItem, PurchaseOrder

RISK_LABELS = {
    "critical": "Critical",
    "low_stock": "Low stock",
    "no_demand_data": "No demand data",
    "normal": "Normal",
    "overstock": "Overstock",
}
MAX_LIST = 25
# Orders not yet closed. Draft and pending orders are not yet committed to a
# supplier, so they are listed here but do not reduce stock-risk quantities.
OUTSTANDING_STATUSES = ("draft", "pending", "approved", "ordered", "partially_received")


def fmt(value, places: int = 2, unit: str = "") -> str:
    if value is None:
        return "not available"
    if isinstance(value, (Decimal, float, int)):
        text = f"{float(value):,.{places}f}"
        if places and text.endswith("." + "0" * places):
            text = text[: -(places + 1)]
    else:
        text = str(value)
    return f"{text} {unit}".strip()


def money(value) -> str:
    """Currency is always shown with two decimal places."""
    return f"{float(value or 0):,.2f}"


def active_items(db: Session) -> list[InventoryItem]:
    return list(db.scalars(select(InventoryItem).where(InventoryItem.is_active.is_(True)).order_by(InventoryItem.id)).all())


def risk_block(db: Session, item: InventoryItem, explain: bool = False) -> list[str]:
    risk = get_item_stock_risk(db, item.id)
    if risk is None:
        return [f"Stock risk for {item.item_code} ({item.item_name}) could not be calculated."]
    unit = item.unit_of_measure
    lines = [
        f"Stock risk for {item.item_code} ({item.item_name}): {RISK_LABELS[risk['risk_level']]}.",
        f"- Available stock: {fmt(risk['available_quantity'], 3, unit)}.",
        f"- Average daily consumption: {fmt(risk['average_daily_consumption'], 3, unit)}"
        + (f" (over {risk['observed_days']} tracked days)." if risk["observed_days"] else " (no consumption recorded)."),
        f"- Days of cover: {fmt(risk['days_of_cover'], 1, 'days')}.",
        f"- Lead time: {risk['lead_time_days']} days.",
        f"- Reorder point: {fmt(risk['calculated_reorder_point'], 3, unit)}.",
        f"- Open purchase orders not yet received: {fmt(risk['outstanding_open_po_quantity'], 3, unit)}.",
        f"- Suggested order quantity: {fmt(risk['suggested_order_quantity'], 3, unit)}"
        + (" (replenishment required)." if risk["requires_replenishment"] else " (no order needed; open orders cover the reorder point)."),
    ]
    if explain:
        lines += [
            "",
            "How this was calculated:",
            f"- Reorder point = average daily consumption x lead time + safety stock "
            f"= {fmt(risk['average_daily_consumption'], 3)} x {risk['lead_time_days']} + {fmt(risk['safety_stock'], 3)}, "
            f"not lower than the configured reorder level ({fmt(risk['reorder_level'], 3)}).",
            f"- Risk is Critical when days of cover ({fmt(risk['days_of_cover'], 1)}) is within the lead time, "
            "Low stock when available stock is at or below the reorder point, and Overstock when cover exceeds "
            f"{risk['overstock_threshold_days']} days.",
            f"- Suggested order = reorder point minus inventory position ({fmt(risk['inventory_position'], 3, unit)}, "
            "available stock plus open purchase orders).",
        ]
    return lines


def stock_risk_answer(db: Session, items: list[InventoryItem], explain: bool = False):
    sections = []
    for item in items[:3]:
        sections.append("\n".join(risk_block(db, item, explain=explain)))
    if len(items) > 3:
        sections.append(f"Showing the first 3 of {len(items)} items. Ask about a specific item for more detail.")
    return "\n\n".join(sections), ["Inventory database", "Consumption analytics", "Stock-risk engine"]


def risk_ranking_answer(db: Session):
    rows = []
    for item in active_items(db):
        risk = get_item_stock_risk(db, item.id)
        if risk is not None:
            rows.append((risk, item))
    if not rows:
        return "There are no active inventory items to assess.", ["Inventory database"]
    rows.sort(key=lambda r: (RISK_RANK[r[0]["risk_level"]], r[0]["days_of_cover"] if r[0]["days_of_cover"] is not None else Decimal("999999")))
    lines = []
    for risk, item in rows[:MAX_LIST]:
        status = RISK_LABELS[risk["risk_level"]]
        order = (
            f"; suggested order {fmt(risk['suggested_order_quantity'], 3, item.unit_of_measure)}"
            if risk["requires_replenishment"] else ""
        )
        lines.append(
            f"- {item.item_code} ({item.item_name}): {status}; "
            f"{fmt(risk['available_quantity'], 3, item.unit_of_measure)} available; "
            f"{fmt(risk['days_of_cover'], 1, 'days')} of cover{order}."
        )
    needing = sum(1 for r, _ in rows if r["requires_replenishment"])
    header = f"Stock risk across {len(rows)} active items ({needing} need replenishment), most urgent first:"
    return header + "\n" + "\n".join(lines), ["Inventory database", "Consumption analytics", "Stock-risk engine"]


def forecast_answer(db: Session, item: InventoryItem):
    forecast = generate_three_month_forecast(db, item.id)
    if forecast is None:
        return f"I could not find an active forecast for {item.item_code}.", ["Demand forecasting engine"]
    unit = item.unit_of_measure
    if forecast["status"] == "insufficient_data":
        return (
            f"Demand forecast for {item.item_code} ({item.item_name}): not available yet.\n"
            f"{forecast['status_message']}",
            ["Consumption database", "Demand forecasting engine"],
        )
    history = "\n".join(
        f"- {p['start_date']} to {p['end_date']}: {fmt(p['total_consumption'], 3, unit)} consumed."
        for p in forecast["historical_periods"]
    )
    if forecast["status"] == "no_demand":
        return (
            f"Demand forecast for {item.item_code} ({item.item_name}): zero.\n"
            f"{forecast['status_message']}\n"
            f"Historical demand (last three complete 30-day periods):\n{history}",
            ["Consumption database", "Demand forecasting engine"],
        )
    lines = "\n".join(
        f"- Period {p['forecast_period']} ({p['start_date']} to {p['end_date']}): {fmt(p['predicted_demand'], 3, unit)}."
        for p in forecast["forecasts"]
    )
    return (
        f"Demand forecast for {item.item_code} ({item.item_name}):\n"
        f"Average demand per 30-day period: {fmt(forecast['average_monthly_demand'], 3, unit)}.\n"
        f"{lines}\n"
        f"Method: {forecast['method']}.\n"
        f"Historical demand:\n{history}\n{forecast['status_message']}",
        ["Consumption database", "Three-period moving-average forecast"],
    )


def planning_answer(db: Session, item: InventoryItem):
    planning = get_planning_demand(db, item.id)
    if planning is None:
        return f"I could not find an active item {item.item_code} for planning.", ["Demand planning engine"]
    unit = item.unit_of_measure
    if planning["forecast_status"] != "ok" and planning["forecast_status"] != "no_demand":
        return (
            f"Planning demand for {item.item_code}: not available yet.\n{planning['status_message']}",
            ["Forecasting engine", "Forecast override database"],
        )
    lines = []
    for p in planning["planning_periods"]:
        status = {
            "ai_forecast": "AI forecast",
            "manually_adjusted": f"manually adjusted by {p['adjusted_by']}"
            + (f" ({p['adjustment_reason']})" if p["adjustment_reason"] else ""),
            "no_forecast": "no forecast",
        }[p["adjustment_status"]]
        original = (
            f" (AI forecast was {fmt(p['original_ai_demand'], 3, unit)})"
            if p["adjustment_status"] == "manually_adjusted" else ""
        )
        lines.append(
            f"- Period {p['forecast_period']} ({p['start_date']} to {p['end_date']}): "
            f"{fmt(p['final_planning_demand'], 3, unit)}; {status}{original}."
        )
    return (
        f"Planning demand for {item.item_code} ({item.item_name}):\n" + "\n".join(lines)
        + "\nThe original AI forecast is never changed; overrides only affect planning.",
        ["Forecasting engine", "Forecast override database"],
    )


def purchase_orders_answer(db: Session, item: InventoryItem | None, open_only: bool):
    query = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
    if item is not None:
        query = query.where(PurchaseOrder.inventory_item_id == item.id)
    if open_only:
        query = query.where(PurchaseOrder.status.in_(OUTSTANDING_STATUSES))
    orders = list(db.scalars(query.limit(MAX_LIST + 1)).all())
    scope = f"for {item.item_code} ({item.item_name}) " if item else ""
    qualifier = "open " if open_only else ""
    if not orders:
        return f"No {qualifier}purchase orders were found {scope}.".replace("  ", " ").strip(), ["Purchase order database"]
    lines = []
    for order in orders[:MAX_LIST]:
        lines.append(
            f"- {order.po_number}: {order.status.replace('_', ' ').title()}; supplier: {order.supplier_name}; "
            f"ordered {fmt(order.ordered_quantity, 3)}; received {fmt(order.received_quantity, 3)}; "
            f"remaining {fmt(order.remaining_quantity, 3)}."
        )
    more = "\nShowing the 25 most recent; there are more." if len(orders) > MAX_LIST else ""
    note = (
        "\nDraft and pending orders are not yet committed to a supplier, so they are not counted as incoming stock."
        if open_only else ""
    )
    return f"Purchase orders {scope}({len(orders[:MAX_LIST])} shown):\n" + "\n".join(lines) + more + note, ["Purchase order database"]


def inventory_detail_answer(item: InventoryItem):
    unit = item.unit_of_measure
    return (
        f"Inventory details for {item.item_code} ({item.item_name}):\n"
        f"- Category: {item.category or 'Uncategorized'}.\n"
        f"- On hand: {fmt(item.on_hand_quantity, 3, unit)}.\n"
        f"- Reserved: {fmt(item.reserved_quantity, 3, unit)}.\n"
        f"- Available: {fmt(item.available_quantity, 3, unit)}.\n"
        f"- Reorder level: {fmt(item.reorder_level, 3, unit)}.\n"
        f"- Safety stock: {fmt(item.safety_stock, 3, unit)}.\n"
        f"- Lead time: {item.lead_time_days} days.\n"
        f"- Unit cost: {money(item.unit_cost)}.",
        ["Inventory database"],
    )


def inventory_summary_answer(db: Session):
    items = active_items(db)
    if not items:
        return "There are no active inventory items.", ["Inventory database"]
    lines = [
        f"- {i.item_code} ({i.item_name}): {fmt(i.available_quantity, 3, i.unit_of_measure)} available "
        f"of {fmt(i.on_hand_quantity, 3, i.unit_of_measure)} on hand."
        for i in items[:MAX_LIST]
    ]
    more = f"\nShowing {MAX_LIST} of {len(items)} items." if len(items) > MAX_LIST else ""
    return f"Current inventory position ({len(items)} active items):\n" + "\n".join(lines) + more, ["Inventory database"]


def valuation_answer(db: Session, item: InventoryItem | None):
    items = [item] if item else active_items(db)
    total = Decimal("0")
    for i in items:
        total += Decimal(str(i.on_hand_quantity)) * Decimal(str(i.unit_cost))
    if item:
        return (
            f"On-hand value of {item.item_code} ({item.item_name}): "
            f"{money(Decimal(str(item.on_hand_quantity)) * Decimal(str(item.unit_cost)))} "
            f"(on hand {fmt(item.on_hand_quantity, 3, item.unit_of_measure)} x unit cost {money(item.unit_cost)}).",
            ["Inventory database"],
        )
    return f"Total on-hand inventory value across {len(items)} active items: {money(total)}.", ["Inventory database"]


def scenario_answer(db: Session, item: InventoryItem, percent: float):
    risk = get_item_stock_risk(db, item.id)
    if risk is None:
        return f"I could not model a scenario for {item.item_code}.", ["Stock-risk engine"]
    base = Decimal(str(risk["average_daily_consumption"]))
    if base == 0:
        return (
            f"I can't model a demand change for {item.item_code} yet because no consumption has been recorded.",
            ["Consumption database"],
        )
    factor = Decimal(str(1 + percent / 100))
    scen_daily = quantize_qty(base * factor)
    lead = item.lead_time_days
    rop = calculate_reorder_point(scen_daily, lead, Decimal(str(item.safety_stock)), Decimal(str(item.reorder_level)))
    cover = calculate_days_of_cover(risk["available_quantity"], scen_daily)
    level = classify_risk(scen_daily, risk["available_quantity"], cover, lead, rop, risk["overstock_threshold_days"])
    suggested = calculate_suggested_order(rop, risk["inventory_position"])
    direction = "increase" if percent >= 0 else "decrease"
    unit = item.unit_of_measure
    return (
        f"What-if: demand {direction}s by {abs(percent):g}% for {item.item_code} ({item.item_name}). "
        "This is a simulation only; no live records were changed.\n"
        f"- Average daily demand: {fmt(base, 3, unit)} now, {fmt(scen_daily, 3, unit)} in the scenario.\n"
        f"- Days of cover: {fmt(risk['days_of_cover'], 1)} now, {fmt(cover, 1)} in the scenario.\n"
        f"- Reorder point: {fmt(risk['calculated_reorder_point'], 3, unit)} now, {fmt(rop, 3, unit)} in the scenario.\n"
        f"- Risk level: {RISK_LABELS[risk['risk_level']]} now, {RISK_LABELS[level]} in the scenario.\n"
        f"- Suggested order: {fmt(risk['suggested_order_quantity'], 3, unit)} now, {fmt(suggested, 3, unit)} in the scenario.",
        ["Stock-risk engine", "What-if simulation (not saved)"],
    )
