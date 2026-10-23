"""
StockSense AI - Inventory Models (Batches & Stock Movements)
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import (
    String, DateTime, Integer, ForeignKey, Text, Numeric, Date, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InventoryBatch(Base):
    """
    Represents a batch of product stock.
    Stock is tracked at the batch level, not at the product level.
    Remaining quantity is updated transactionally.
    """
    __tablename__ = "inventory_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    batch_number: Mapped[str] = mapped_column(String(100), nullable=True)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    manufacture_date: Mapped[date] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=True)
    receipt_reference: Mapped[str] = mapped_column(String(100), nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # PURCHASE, OPENING, ADJUSTMENT
    source_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="batches")
    movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="batch"
    )

    __table_args__ = (
        Index("ix_batch_product_expiry", "product_id", "expiry_date"),
        Index("ix_batch_source", "source_type", "source_id"),
    )


class StockMovement(Base):
    """
    Audit log for every stock change. Positive quantity = stock in,
    negative quantity = stock out. Every inventory mutation must
    generate a movement record.
    """
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inventory_batches.id"), nullable=True
    )
    movement_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # RECEIPT, SALE, ADJUSTMENT, DAMAGE, CORRECTION, OPENING, REVERSAL
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )  # positive=in, negative=out
    reference_type: Mapped[str] = mapped_column(
        String(30), nullable=True
    )  # SALE, PURCHASE, ADJUSTMENT, etc.
    reference_id: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="stock_movements")
    batch: Mapped["InventoryBatch"] = relationship("InventoryBatch", back_populates="movements")

    __table_args__ = (
        Index("ix_movement_ref", "reference_type", "reference_id"),
        Index("ix_movement_type_date", "movement_type", "created_at"),
    )
