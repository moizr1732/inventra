from sqlalchemy import select
from sqlalchemy.orm import Session

from app.forecasting.demand_forecast import generate_three_month_forecast
from app.models import ForecastOverride


def get_planning_demand(db: Session, item_id: int, today=None):
    """Final planning demand per period.

    A manual override, when one exists for the period, replaces the AI
    prediction for planning. The original AI forecast is never modified and
    is always returned alongside the planning value for transparency.
    """
    forecast = generate_three_month_forecast(db=db, item_id=item_id, today=today)
    if forecast is None:
        return None

    overrides = db.scalars(
        select(ForecastOverride).where(ForecastOverride.inventory_item_id == item_id)
    ).all()
    override_by_start = {o.forecast_start_date: o for o in overrides}

    planning_periods = []
    for period in forecast["forecasts"]:
        original = period["predicted_demand"]
        override = override_by_start.get(period["start_date"])

        if override is not None:
            final = override.adjusted_demand
            status = "manually_adjusted"
            adjusted = override.adjusted_demand
            adjusted_by = override.adjusted_by
            reason = override.reason
        elif original is None:
            final = None
            status = "no_forecast"
            adjusted = None
            adjusted_by = None
            reason = None
        else:
            final = original
            status = "ai_forecast"
            adjusted = None
            adjusted_by = None
            reason = None

        planning_periods.append({
            "forecast_period": period["forecast_period"],
            "start_date": period["start_date"],
            "end_date": period["end_date"],
            "original_ai_demand": original,
            "adjusted_demand": adjusted,
            "final_planning_demand": final,
            "adjustment_status": status,
            "adjusted_by": adjusted_by,
            "adjustment_reason": reason,
        })

    return {
        "item_id": forecast["item_id"],
        "item_code": forecast["item_code"],
        "item_name": forecast["item_name"],
        "unit_of_measure": forecast["unit_of_measure"],
        "forecast_status": forecast["status"],
        "status_message": forecast["status_message"],
        "planning_horizon": forecast["forecast_horizon"],
        "planning_periods": planning_periods,
    }
