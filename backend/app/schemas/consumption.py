
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ConsumptionCreate(BaseModel):
    inventory_item_id: int = Field(gt=0)
    consumption_date: date
    quantity_consumed: Decimal = Field(gt=0)
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


class ConsumptionResponse(ConsumptionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
