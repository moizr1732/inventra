
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.forecasting.planning_demand import get_planning_demand
from app.database.session import get_db
from app.models import InventoryItem, ForecastOverride
from app.schemas import (
    ForecastOverrideCreate,
    ForecastOverrideResponse,
)
from app.forecasting.demand_forecast import (
    generate_three_month_forecast,
)

router = APIRouter(
    prefix="/forecasting",
    tags=["Demand Forecasting"],
)


@router.get("/{item_id}")
def get_demand_forecast(
    item_id: int,
    db: Session = Depends(get_db),
):
    forecast = generate_three_month_forecast(
        db=db,
        item_id=item_id,
    )

    if forecast is None:
        raise HTTPException(
            status_code=404,
            detail="Active inventory item not found.",
        )

    return forecast


@router.post(
    "/{item_id}/overrides",
    response_model=ForecastOverrideResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_forecast_override(
    item_id: int,
    override_data: ForecastOverrideCreate,
    db: Session = Depends(get_db),
):
    item = db.get(InventoryItem, item_id)

    if item is None or not item.is_active:
        raise HTTPException(
            status_code=404,
            detail="Active inventory item not found.",
        )

    forecast = generate_three_month_forecast(
        db=db,
        item_id=item_id,
    )

    if forecast is None:
        raise HTTPException(
            status_code=404,
            detail="Forecast not found.",
        )

    matching_period = next(
        (
            period
            for period in forecast["forecasts"]
            if (
                period["start_date"] == override_data.forecast_start_date
                and period["end_date"] == override_data.forecast_end_date
            )
        ),
        None,
    )

    if matching_period is None:
        raise HTTPException(
            status_code=422,
            detail="The supplied dates do not match a forecast period.",
        )

    if (
        override_data.original_predicted_demand
        != matching_period["predicted_demand"]
    ):
        raise HTTPException(
            status_code=409,
            detail="Original predicted demand does not match the current AI forecast.",
        )

    existing_override = db.scalar(
        select(ForecastOverride).where(
            ForecastOverride.inventory_item_id == item_id,
            ForecastOverride.forecast_start_date
            == override_data.forecast_start_date,
        )
    )

    if existing_override is not None:
        raise HTTPException(
            status_code=409,
            detail="An override already exists for this forecast period.",
        )

    new_override = ForecastOverride(
        inventory_item_id=item_id,
        **override_data.model_dump(),
    )

    db.add(new_override)
    db.commit()
    db.refresh(new_override)

    return new_override




@router.get(
    "/{item_id}/overrides",
    response_model=list[ForecastOverrideResponse],
)
def get_forecast_overrides(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = db.get(InventoryItem, item_id)

    if item is None or not item.is_active:
        raise HTTPException(
            status_code=404,
            detail="Active inventory item not found.",
        )

    statement = (
        select(ForecastOverride)
        .where(
            ForecastOverride.inventory_item_id == item_id
        )
        .order_by(ForecastOverride.forecast_start_date)
    )

    return db.scalars(statement).all()



@router.get("/{item_id}/planning")
def get_item_planning_demand(
    item_id: int,
    db: Session = Depends(get_db),
):
    planning = get_planning_demand(
        db=db,
        item_id=item_id,
    )

    if planning is None:
        raise HTTPException(
            status_code=404,
            detail="Active inventory item not found.",
        )

    return planning
