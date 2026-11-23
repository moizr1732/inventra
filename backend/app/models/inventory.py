
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    __table_args__ = (
        CheckConstraint(
            "on_hand_quantity >= 0",
            name="ck_inventory_on_hand_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity >= 0",
            name="ck_inventory_reserved_nonnegative",
        ),
        CheckConstraint(
            "reorder_level >= 0",
            name="ck_inventory_reorder_nonnegative",
        ),
        CheckConstraint(
            "safety_stock >= 0",
            name="ck_inventory_safety_nonnegative",
        ),
        CheckConstraint(
            "lead_time_days >= 0",
            name="ck_inventory_lead_time_nonnegative",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_inventory_unit_cost_nonnegative",
        ),
        CheckConstraint(
            "reserved_quantity <= on_hand_quantity",
            name="ck_inventory_reserved_not_above_on_hand",
        ),
        Index("ix_inventory_item_name", "item_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    item_code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    item_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    category: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(30),
        default="pcs",
        nullable=False,
    )

    on_hand_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        default=Decimal("0"),
        nullable=False,
    )

    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        default=Decimal("0"),
        nullable=False,
    )

    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        default=Decimal("0"),
        nullable=False,
    )

    safety_stock: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        default=Decimal("0"),
        nullable=False,
    )

    lead_time_days: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=Decimal("0"),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
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

    @property
    def available_quantity(self) -> Decimal:
        return self.on_hand_quantity - self.reserved_quantity
