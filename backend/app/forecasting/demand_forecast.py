
from decimal import Decimal
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryItem, InventoryConsumption


def calculate_three_month_average(
    monthly_demand: list[Decimal],
) -> Decimal:
    """
    Calculate average demand from the three most recent months.
    """

    if len(monthly_demand) < 3:
        raise ValueError(
            "At least three months of demand data are required."
        )

    recent_months = monthly_demand[-3:]

    average_demand = sum(recent_months) / Decimal("3")

    return average_demand.quantize(Decimal("0.001"))


def get_three_month_demand_history(
    db: Session,
    item_id: int,
):
    """
    Retrieve consumption history for three consecutive
    30-day periods from the database.
    """

    item = db.get(InventoryItem, item_id)

    if item is None or not item.is_active:
        return None

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=89)

    statement = (
        select(InventoryConsumption)
        .where(
            InventoryConsumption.inventory_item_id == item_id,
            InventoryConsumption.consumption_date >= start_date,
            InventoryConsumption.consumption_date <= end_date,
        )
        .order_by(InventoryConsumption.consumption_date)
    )

    records = db.scalars(statement).all()

    period_totals = [
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
    ]

    for record in records:
        days_from_start = (
            record.consumption_date - start_date
        ).days

        period_index = min(days_from_start // 30, 2)

        period_totals[period_index] += Decimal(
            str(record.quantity_consumed)
        )

    periods = []

    for index, total in enumerate(period_totals):
        period_start = start_date + timedelta(days=index * 30)
        period_end = period_start + timedelta(days=29)

        periods.append({
            "period": index + 1,
            "start_date": period_start,
            "end_date": period_end,
            "total_consumption": total,
        })

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "historical_periods": periods,
        "total_records": len(records),
    }


def generate_three_month_forecast(
    db: Session,
    item_id: int,
):
    """
    Generate a three-period demand forecast
    using the three-month moving average.
    """

    history = get_three_month_demand_history(
        db=db,
        item_id=item_id,
    )

    if history is None:
        return None

    historical_demand = [
        period["total_consumption"]
        for period in history["historical_periods"]
    ]

    if any(demand <= 0 for demand in historical_demand):
        raise ValueError(
            "All three historical periods must have demand data."
        )

    average_demand = calculate_three_month_average(
        historical_demand
    )

    forecasts = []

    forecast_start = date.today()

    for period in range(1, 4):
        period_start = forecast_start + timedelta(
            days=(period - 1) * 30
        )

        period_end = period_start + timedelta(days=29)

        forecasts.append({
            "forecast_period": period,
            "start_date": period_start,
            "end_date": period_end,
            "predicted_demand": average_demand,
        })

    return {
        "item_id": history["item_id"],
        "item_code": history["item_code"],
        "item_name": history["item_name"],
        "historical_demand": historical_demand,
        "average_monthly_demand": average_demand,
        "forecast_horizon": "Next three 30-day periods",
        "forecasts": forecasts,
    }
