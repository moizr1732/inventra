
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.inventory.stock_risk import get_item_stock_risk

from app.database.session import get_db
from app.models import InventoryItem
from app.schemas import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post(
    "",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_item(
    item: InventoryItemCreate,
    db: Session = Depends(get_db),
):
    existing_item = db.scalar(
        select(InventoryItem).where(
            InventoryItem.item_code == item.item_code
        )
    )

    if existing_item:
        raise HTTPException(
            status_code=409,
            detail="An inventory item with this item code already exists.",
        )

    new_item = InventoryItem(**item.model_dump())

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return new_item


@router.get("", response_model=list[InventoryItemResponse])
def get_inventory_items(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    statement = (
        select(InventoryItem)
        .where(InventoryItem.is_active.is_(True))
        .order_by(InventoryItem.id)
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get("/{item_id}", response_model=InventoryItemResponse)
def get_inventory_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = db.get(InventoryItem, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")

    return item


@router.patch("/{item_id}", response_model=InventoryItemResponse)
def update_inventory_item(
    item_id: int,
    updates: InventoryItemUpdate,
    db: Session = Depends(get_db),
):
    item = db.get(InventoryItem, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")

    changes = updates.model_dump(exclude_unset=True)

    new_on_hand = changes.get("on_hand_quantity", item.on_hand_quantity)
    new_reserved = changes.get("reserved_quantity", item.reserved_quantity)

    if new_on_hand is None or new_reserved is None:
        raise HTTPException(
            status_code=422,
            detail="Stock quantities cannot be null.",
        )

    if new_reserved > new_on_hand:
        raise HTTPException(
            status_code=422,
            detail="Reserved quantity cannot exceed on-hand quantity.",
        )

    for field, value in changes.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)

    return item


@router.get("/{item_id}/risk")
def get_inventory_item_risk(
    item_id: int,
    days: int = Query(default=90, ge=1, le=365),
    overstock_days: int = Query(default=60, ge=1, le=365),
    db: Session = Depends(get_db),
):
    risk = get_item_stock_risk(
        db=db,
        item_id=item_id,
        days=days,
        overstock_days=overstock_days,
    )

    if risk is None:
        raise HTTPException(
            status_code=404,
            detail="Active inventory item not found.",
        )

    return risk