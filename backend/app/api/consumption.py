
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.inventory.consumption_analytics import get_consumption_analytics
from app.database.session import get_db
from app.models import InventoryItem, InventoryConsumption
from app.schemas import ConsumptionCreate, ConsumptionResponse

router = APIRouter(prefix="/consumption", tags=["Consumption"])


@router.post(
    "",
    response_model=ConsumptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_consumption_record(
    record: ConsumptionCreate,
    db: Session = Depends(get_db),
):
    item = db.get(InventoryItem, record.inventory_item_id)

    if item is None or not item.is_active:
        raise HTTPException(
            status_code=404,
            detail="Active inventory item not found.",
        )

    if record.quantity_consumed > item.available_quantity:
        raise HTTPException(
            status_code=422,
            detail="Consumption cannot exceed available stock.",
        )

    new_record = InventoryConsumption(**record.model_dump())

    item.on_hand_quantity -= record.quantity_consumed

    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return new_record


@router.get("", response_model=list[ConsumptionResponse])
def get_consumption_records(
    inventory_item_id: int | None = Query(default=None, gt=0),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    statement = select(InventoryConsumption)

    if inventory_item_id is not None:
        statement = statement.where(
            InventoryConsumption.inventory_item_id == inventory_item_id
        )

    statement = (
        statement
        .order_by(InventoryConsumption.consumption_date.desc())
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()



@router.get("/analytics/{item_id}")
def get_item_consumption_analytics(
    item_id: int,
    days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    analytics = get_consumption_analytics(
        db=db,
        item_id=item_id,
        days=days,
    )

    if analytics is None:
        raise HTTPException(
            status_code=404,
            detail="Active inventory item not found.",
        )

    return analytics