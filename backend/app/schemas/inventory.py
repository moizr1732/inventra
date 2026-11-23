from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InventoryItemBase(BaseModel):
    item_code: str = Field(min_length=1, max_length=100)
    item_name: str = Field(min_length=1, max_length=255)

    category: str | None = Field(default=None, max_length=150)

    unit_of_measure: str = Field(default="pcs", max_length=30)

    on_hand_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    reserved_quantity: Decimal = Field(default=Decimal("0"), ge=0)

    reorder_level: Decimal = Field(default=Decimal("0"), ge=0)
    safety_stock: Decimal = Field(default=Decimal("0"), ge=0)

    lead_time_days: int = Field(default=0, ge=0)

    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def validate_reserved_stock(self):
        if self.reserved_quantity > self.on_hand_quantity:
            raise ValueError(
                "Reserved quantity cannot exceed on-hand quantity."
            )
        return self


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    item_name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=150)
    unit_of_measure: str | None = Field(default=None, max_length=30)

    on_hand_quantity: Decimal | None = Field(default=None, ge=0)
    reserved_quantity: Decimal | None = Field(default=None, ge=0)

    reorder_level: Decimal | None = Field(default=None, ge=0)
    safety_stock: Decimal | None = Field(default=None, ge=0)

    lead_time_days: int | None = Field(default=None, ge=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)

    is_active: bool | None = None


class InventoryItemResponse(InventoryItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    available_quantity: Decimal
