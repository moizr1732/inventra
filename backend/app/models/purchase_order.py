
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


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    __table_args__ = (
        CheckConstraint(
            "ordered_quantity > 0",
            name="ck_po_ordered_quantity_positive",
        ),
        CheckConstraint(
            "received_quantity >= 0",
            name="ck_po_received_quantity_nonnegative",
        ),
        CheckConstraint(
            "received_quantity <= ordered_quantity",
            name="ck_po_received_not_above_ordered",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_po_unit_cost_nonnegative",
        ),
        CheckConstraint(
            "status IN ('draft', 'pending', 'approved', 'ordered', "
            "'partially_received', 'received', 'cancelled')",
            name="ck_po_valid_status",
        ),
        Index(
            "ix_purchase_order_item_status",
            "inventory_item_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    po_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    supplier_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    ordered_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        default=Decimal("0"),
        nullable=False,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=Decimal("0"),
        nullable=False,
    )

    order_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    expected_delivery_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        nullable=False,
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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def remaining_quantity(self) -> Decimal:
        return self.ordered_quantity - self.received_quantity
