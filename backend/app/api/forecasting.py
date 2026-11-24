from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.forecasting.demand_forecast import generate_three_month_forecast
from app.forecasting.planning_demand import get_planning_demand
from app.models import ForecastOverride, InventoryItem
from app.schemas import ForecastOverrideCreate, ForecastOverrideResponse

router = APIRouter(prefix="/forecasting", tags=["Demand Forecasting"])


def _active_item_or_404(db: Session, item_id: int) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="Active inventory item not found.")
    return item


@router.get("/{item_id}")
def get_demand_forecast(item_id: int, db: Session = Depends(get_db)):
    forecast = generate_three_month_forecast(db=db, item_id=item_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail="Active inventory item not found.")
    return forecast


@router.post("/{item_id}/overrides", response_model=ForecastOverrideResponse, status_code=status.HTTP_201_CREATED)
def create_forecast_override(item_id: int, override_data: ForecastOverrideCreate, db: Session = Depends(get_db)):
    _active_item_or_404(db, item_id)

    forecast = generate_three_month_forecast(db=db, item_id=item_id)
    matching = next(
        (
            p for p in forecast["forecasts"]
            if p["start_date"] == override_data.forecast_start_date
            and p["end_date"] == override_data.forecast_end_date
        ),
        None,
    )
    if matching is None:
        raise HTTPException(
            status_code=422,
            detail="The supplied dates do not match a current forecast period.",
        )
    if matching["predicted_demand"] is None:
        raise HTTPException(status_code=422, detail="No forecast exists for this period, so it cannot be overridden.")

    if override_data.original_predicted_demand != matching["predicted_demand"]:
        raise HTTPException(
            status_code=409,
            detail="Original predicted demand does not match the current AI forecast. Refresh and try again.",
        )

    new_override = ForecastOverride(inventory_item_id=item_id, **override_data.model_dump())
    db.add(new_override)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An override already exists for this forecast period.")
    db.refresh(new_override)
    return new_override


@router.get("/{item_id}/overrides", response_model=list[ForecastOverrideResponse])
def get_forecast_overrides(item_id: int, db: Session = Depends(get_db)):
    _active_item_or_404(db, item_id)
    return db.scalars(
        select(ForecastOverride)
        .where(ForecastOverride.inventory_item_id == item_id)
        .order_by(ForecastOverride.forecast_start_date)
    ).all()


@router.delete("/{item_id}/overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_forecast_override(item_id: int, override_id: int, db: Session = Depends(get_db)):
    override = db.scalar(
        select(ForecastOverride).where(
            ForecastOverride.id == override_id,
            ForecastOverride.inventory_item_id == item_id,
        )
    )
    if override is None:
        raise HTTPException(status_code=404, detail="Forecast override not found.")
    db.delete(override)
    db.commit()
    return None


@router.get("/{item_id}/planning")
def get_item_planning_demand(item_id: int, db: Session = Depends(get_db)):
    planning = get_planning_demand(db=db, item_id=item_id)
    if planning is None:
        raise HTTPException(status_code=404, detail="Active inventory item not found.")
    return planning
