
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class InventoryConsumption(Base):
    __tablename__ = "inventory_consumption"

    __table_args__ = (
        CheckConstraint(
            "quantity_consumed > 0",
            name="ck_consumption_quantity_positive",
        ),
        Index(
            "ix_consumption_item_date",
            "inventory_item_id",
            "consumption_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    consumption_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    quantity_consumed: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
