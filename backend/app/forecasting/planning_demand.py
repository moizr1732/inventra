
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ForecastOverride
from app.forecasting.demand_forecast import (
    generate_three_month_forecast,
)


def get_planning_demand(
    db: Session,
    item_id: int,
):
    """
    Determine the final planning demand for each forecast period.

    If an AGI user has submitted a manual override,
    use the adjusted demand.

    Otherwise, use the original AI prediction.

    The original AI forecast is never modified.
    """

    forecast = generate_three_month_forecast(
        db=db,
        item_id=item_id,
    )

    if forecast is None:
        return None

    statement = (
        select(ForecastOverride)
        .where(
            ForecastOverride.inventory_item_id == item_id
        )
        .order_by(ForecastOverride.forecast_start_date)
    )

    overrides = db.scalars(statement).all()

    override_by_date = {
        override.forecast_start_date: override
        for override in overrides
    }

    planning_periods = []

    for period in forecast["forecasts"]:
        original_demand = period["predicted_demand"]

        override = override_by_date.get(
            period["start_date"]
        )

        if override is not None:
            adjusted_demand = override.adjusted_demand
            final_planning_demand = adjusted_demand
            adjustment_status = "manually_adjusted"
            adjusted_by = override.adjusted_by
            adjustment_reason = override.reason
        else:
            adjusted_demand = None
            final_planning_demand = original_demand
            adjustment_status = "ai_forecast"
            adjusted_by = None
            adjustment_reason = None

        planning_periods.append({
            "forecast_period": period["forecast_period"],
            "start_date": period["start_date"],
            "end_date": period["end_date"],
            "original_ai_demand": original_demand,
            "adjusted_demand": adjusted_demand,
            "final_planning_demand": final_planning_demand,
            "adjustment_status": adjustment_status,
            "adjusted_by": adjusted_by,
            "adjustment_reason": adjustment_reason,
        })

    return {
        "item_id": forecast["item_id"],
        "item_code": forecast["item_code"],
        "item_name": forecast["item_name"],
        "planning_horizon": forecast["forecast_horizon"],
        "planning_periods": planning_periods,
    }
