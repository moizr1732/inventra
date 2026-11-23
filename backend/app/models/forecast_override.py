
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ForecastOverride(Base):
    __tablename__ = "forecast_overrides"

    __table_args__ = (
        CheckConstraint(
            "original_predicted_demand >= 0",
            name="ck_forecast_original_demand_nonnegative",
        ),
        CheckConstraint(
            "adjusted_demand >= 0",
            name="ck_forecast_adjusted_demand_nonnegative",
        ),
        CheckConstraint(
            "forecast_start_date <= forecast_end_date",
            name="ck_forecast_override_valid_dates",
        ),
        UniqueConstraint(
            "inventory_item_id",
            "forecast_start_date",
            name="uq_forecast_override_item_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    forecast_start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    forecast_end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    original_predicted_demand: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    adjusted_demand: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    adjusted_by: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
