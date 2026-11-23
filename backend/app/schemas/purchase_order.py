
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PurchaseOrderStatus = Literal[
    "draft",
    "pending",
    "approved",
    "ordered",
    "partially_received",
    "received",
    "cancelled",
]


class PurchaseOrderCreate(BaseModel):
    po_number: str = Field(min_length=1, max_length=100)
    inventory_item_id: int = Field(gt=0)
    supplier_name: str = Field(min_length=1, max_length=255)

    ordered_quantity: Decimal = Field(gt=0)
    received_quantity: Decimal = Field(default=Decimal("0"), ge=0)

    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)

    order_date: date
    expected_delivery_date: date | None = None

    status: Literal["draft"] = "draft"
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_purchase_order(self):
        if self.received_quantity > self.ordered_quantity:
            raise ValueError(
                "Received quantity cannot exceed ordered quantity."
            )

        if (
            self.expected_delivery_date is not None
            and self.expected_delivery_date < self.order_date
        ):
            raise ValueError(
                "Expected delivery date cannot be before order date."
            )

        if (
            self.status == "received"
            and self.received_quantity != self.ordered_quantity
        ):
            raise ValueError(
                "A received order must have all its quantity received."
            )

        if (
            self.status == "partially_received"
            and not (
                Decimal("0")
                < self.received_quantity
                < self.ordered_quantity
            )
        ):
            raise ValueError(
                "A partially received order must have some, "
                "but not all, quantity received."
            )

        return self




class PurchaseOrderReceive(BaseModel):
    received_quantity: Decimal = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)


class PurchaseOrderStatusUpdate(BaseModel):
    status: Literal[
        "pending",
        "approved",
        "ordered",
        "cancelled",
    ]


class PurchaseOrderResponse(PurchaseOrderCreate):
    model_config = ConfigDict(from_attributes=True)

    # Responses must support every valid lifecycle status.
    status: PurchaseOrderStatus

    id: int
    created_at: datetime
    updated_at: datetime

    remaining_quantity: Decimal
