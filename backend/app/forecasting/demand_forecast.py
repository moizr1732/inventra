from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.forecasting.periods import (
    HISTORY_PERIODS,
    PERIOD_DAYS,
    forecast_period_starts,
    history_period_starts,
    period_end_for,
)
from app.models import InventoryConsumption, InventoryItem

FORECAST_METHOD = "Three-period moving average over the last three complete 30-day periods"


def calculate_three_month_average(monthly_demand: list[Decimal]) -> Decimal:
    if len(monthly_demand) != HISTORY_PERIODS:
        raise ValueError(f"Exactly {HISTORY_PERIODS} historical periods are required.")
    average = sum(monthly_demand, Decimal("0")) / Decimal(HISTORY_PERIODS)
    return average.quantize(Decimal("0.001"))


def get_three_month_demand_history(db: Session, item_id: int, today: date | None = None):
    item = db.get(InventoryItem, item_id)
    if item is None or not item.is_active:
        return None

    today = today or date.today()
    starts = history_period_starts(today)
    window_start = starts[0]
    window_end = period_end_for(starts[-1])

    records = db.scalars(
        select(InventoryConsumption).where(
            InventoryConsumption.inventory_item_id == item_id,
            InventoryConsumption.consumption_date >= window_start,
            InventoryConsumption.consumption_date <= window_end,
        )
    ).all()

    # Earliest consumption ever recorded. Days before this are untracked, not zero demand.
    tracked_since = db.scalar(
        select(func.min(InventoryConsumption.consumption_date)).where(
            InventoryConsumption.inventory_item_id == item_id
        )
    )

    totals = {start: Decimal("0") for start in starts}
    for record in records:
        for start in starts:
            if start <= record.consumption_date <= period_end_for(start):
                totals[start] += Decimal(str(record.quantity_consumed))
                break

    periods = [
        {
            "period": index + 1,
            "start_date": start,
            "end_date": period_end_for(start),
            "total_consumption": totals[start],
        }
        for index, start in enumerate(starts)
    ]

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "unit_of_measure": item.unit_of_measure,
        "created_on": item.created_at.date() if item.created_at else None,
        "tracked_since": tracked_since,
        "historical_periods": periods,
        "total_records": len(records),
    }


def generate_three_month_forecast(db: Session, item_id: int, today: date | None = None):
    """Forecast the next three 30-day periods.

    Never raises for missing or zero demand. The result always carries a
    `status` the caller can present:

    * ok                 - history is available; predictions are provided.
    * no_demand          - no consumption recorded in the history window.
    * insufficient_data  - the item is too new for a full history window, so
                           no prediction is made.
    """
    today = today or date.today()
    history = get_three_month_demand_history(db, item_id, today=today)
    if history is None:
        return None

    historical_demand = [p["total_consumption"] for p in history["historical_periods"]]
    history_start = history["historical_periods"][0]["start_date"]
    base = {
        "item_id": history["item_id"],
        "item_code": history["item_code"],
        "item_name": history["item_name"],
        "unit_of_measure": history["unit_of_measure"],
        "historical_demand": historical_demand,
        "historical_periods": history["historical_periods"],
        "forecast_horizon": f"Next three {PERIOD_DAYS}-day periods",
        "method": FORECAST_METHOD,
    }

    # Demand can only be judged as zero where consumption was being tracked.
    # Otherwise the missing days are unknown, and averaging them in would understate demand.
    tracked_since = history["tracked_since"]
    created_on = history["created_on"]
    if tracked_since is not None:
        coverage_start = tracked_since
        reason = f"consumption has only been tracked since {tracked_since.isoformat()}"
    elif created_on is not None:
        coverage_start = created_on
        reason = f"the item was created on {created_on.isoformat()}"
    else:
        coverage_start = None
        reason = None

    if coverage_start is not None and coverage_start > history_start:
        available_from = history_start + timedelta(days=HISTORY_PERIODS * PERIOD_DAYS)
        return {
            **base,
            "status": "insufficient_data",
            "status_message": (
                f"{history['item_code']}: {reason}, which is after the start of the "
                f"{HISTORY_PERIODS * PERIOD_DAYS}-day history window ({history_start.isoformat()}). "
                f"A forecast becomes available once a full window is tracked, from about {available_from.isoformat()}."
            ),
            "average_monthly_demand": None,
            "forecasts": [],
        }

    if all(total == 0 for total in historical_demand):
        average = Decimal("0.000")
        status = "no_demand"
        message = (
            "No consumption has been recorded in the last three complete periods, "
            "so the forecast is zero."
        )
    else:
        average = calculate_three_month_average(historical_demand)
        status = "ok"
        zero_periods = sum(1 for total in historical_demand if total == 0)
        message = (
            f"{zero_periods} of the three historical periods had no consumption; "
            "they are included as zero in the average."
            if zero_periods
            else "Forecast based on the last three complete periods of consumption."
        )

    forecasts = [
        {
            "forecast_period": index + 1,
            "start_date": start,
            "end_date": period_end_for(start),
            "predicted_demand": average,
        }
        for index, start in enumerate(forecast_period_starts(today))
    ]

    return {
        **base,
        "status": status,
        "status_message": message,
        "average_monthly_demand": average,
        "forecasts": forecasts,
    }
