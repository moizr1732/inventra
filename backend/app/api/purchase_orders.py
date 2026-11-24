from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.schemas.purchase_order import (
    PurchaseOrderReceive,
    PurchaseOrderStatusUpdate,
)
from app.database.session import get_db
from app.models.inventory import InventoryItem
from app.models.purchase_order import PurchaseOrder
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
)

router = APIRouter(
    prefix="/purchase-orders",
    tags=["Purchase Orders"],
)


@router.post(
    "",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order(
    order_data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
):
    existing_order = db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.po_number == order_data.po_number
        )
    )

    if existing_order:
        raise HTTPException(
            status_code=409,
            detail="Purchase order number already exists.",
        )

    item = db.get(InventoryItem, order_data.inventory_item_id)

    if not item or not item.is_active:
        raise HTTPException(
            status_code=404,
            detail="Active inventory item not found.",
        )

    order = PurchaseOrder(**order_data.model_dump())

    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Purchase order number already exists.")
    db.refresh(order)

    return {
        **order_data.model_dump(),
        "id": order.id,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "remaining_quantity": order.remaining_quantity,
    }


@router.get("", response_model=list[PurchaseOrderResponse])
def get_purchase_orders(
    inventory_item_id: int | None = Query(default=None, gt=0),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(PurchaseOrder).order_by(
        PurchaseOrder.created_at.desc()
    )

    if inventory_item_id is not None:
        query = query.where(
            PurchaseOrder.inventory_item_id == inventory_item_id
        )

    orders = db.scalars(
        query.offset(skip).limit(limit)
    ).all()

    return [
        {
            **{
                field: getattr(order, field)
                for field in [
                    "po_number",
                    "inventory_item_id",
                    "supplier_name",
                    "ordered_quantity",
                    "received_quantity",
                    "unit_cost",
                    "order_date",
                    "expected_delivery_date",
                    "status",
                    "notes",
                ]
            },
            "id": order.id,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "remaining_quantity": order.remaining_quantity,
        }
        for order in orders
    ]


@router.get("/{po_id}", response_model=PurchaseOrderResponse)
def get_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
):
    order = db.get(PurchaseOrder, po_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found.",
        )

    return {
        field: getattr(order, field)
        for field in [
            "id",
            "po_number",
            "inventory_item_id",
            "supplier_name",
            "ordered_quantity",
            "received_quantity",
            "unit_cost",
            "order_date",
            "expected_delivery_date",
            "status",
            "notes",
            "created_at",
            "updated_at",
            "remaining_quantity",
        ]
    }


    
@router.post("/{po_id}/receive", response_model=PurchaseOrderResponse)

def receive_purchase_order(
    po_id: int,
    receipt_data: PurchaseOrderReceive,
    db: Session = Depends(get_db),
):
    try:
        # Lock the purchase order during the transaction.
        order = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .with_for_update()
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Purchase order not found.",
            )

        if order.status not in (
            "approved",
            "ordered",
            "partially_received",
        ):
            raise HTTPException(
                status_code=400,
                detail="This purchase order cannot receive stock in its current status.",
            )

        item = db.scalar(
            select(InventoryItem)
            .where(InventoryItem.id == order.inventory_item_id)
            .with_for_update()
        )

        if not item:
            raise HTTPException(
                status_code=404,
                detail="Associated inventory item not found.",
            )

        # Submitted quantity is the cumulative received quantity.
        new_received_quantity = receipt_data.received_quantity

        if new_received_quantity < order.received_quantity:
            raise HTTPException(
                status_code=409,
                detail="Received quantity cannot be lower than the quantity already recorded.",
            )

        if new_received_quantity > order.ordered_quantity:
            raise HTTPException(
                status_code=400,
                detail="Received quantity cannot exceed the ordered quantity.",
            )

        # Calculate only the additional quantity received.
        receipt_delta = (
            new_received_quantity - order.received_quantity
        )

        if receipt_delta > 0:
            item.on_hand_quantity += receipt_delta
            order.received_quantity = new_received_quantity

            if receipt_data.notes:
                order.notes = (
                    f"{order.notes}\n{receipt_data.notes}"
                    if order.notes
                    else receipt_data.notes
                )

        # Update order status.
        if new_received_quantity == order.ordered_quantity:
            order.status = "received"
        else:
            order.status = "partially_received"

        db.commit()
        db.refresh(order)

        return {
            "po_number": order.po_number,
            "inventory_item_id": order.inventory_item_id,
            "supplier_name": order.supplier_name,
            "ordered_quantity": order.ordered_quantity,
            "received_quantity": order.received_quantity,
            "unit_cost": order.unit_cost,
            "order_date": order.order_date,
            "expected_delivery_date": order.expected_delivery_date,
            "status": order.status,
            "notes": order.notes,
            "id": order.id,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "remaining_quantity": order.remaining_quantity,
        }

    except Exception:
        db.rollback()
        raise


@router.patch("/{po_id}/status", response_model=PurchaseOrderResponse)
def update_purchase_order_status(
    po_id: int,
    status_data: PurchaseOrderStatusUpdate,
    db: Session = Depends(get_db),
):
    try:
        order = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .with_for_update()
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Purchase order not found.",
            )

        current_status = order.status
        new_status = status_data.status

        allowed_transitions = {
            "draft": ["pending", "cancelled"],
            "pending": ["approved", "cancelled"],
            "approved": ["ordered", "cancelled"],
            "ordered": ["cancelled"],
            "partially_received": [],
            "received": [],
            "cancelled": [],
        }

        if new_status not in allowed_transitions.get(current_status, []):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Invalid status transition: "
                    f"{current_status} -> {new_status}."
                ),
            )

        if (
            new_status == "cancelled"
            and order.received_quantity > 0
        ):
            raise HTTPException(
                status_code=409,
                detail="A purchase order with received stock cannot be cancelled.",
            )

        order.status = new_status

        db.commit()
        db.refresh(order)

        return {
            "po_number": order.po_number,
            "inventory_item_id": order.inventory_item_id,
            "supplier_name": order.supplier_name,
            "ordered_quantity": order.ordered_quantity,
            "received_quantity": order.received_quantity,
            "unit_cost": order.unit_cost,
            "order_date": order.order_date,
            "expected_delivery_date": order.expected_delivery_date,
            "status": order.status,
            "notes": order.notes,
            "id": order.id,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "remaining_quantity": order.remaining_quantity,
        }

    except Exception:
        db.rollback()
        raise
