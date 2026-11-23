
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ForecastOverrideCreate(BaseModel):
    forecast_start_date: date
    forecast_end_date: date

    original_predicted_demand: Decimal = Field(ge=0)
    adjusted_demand: Decimal = Field(ge=0)

    adjusted_by: str = Field(min_length=1, max_length=150)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_forecast_dates(self):
        if self.forecast_start_date > self.forecast_end_date:
            raise ValueError(
                "Forecast start date cannot be after end date."
            )

        return self


class ForecastOverrideResponse(ForecastOverrideCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_item_id: int
    created_at: datetime
    updated_at: datetime
