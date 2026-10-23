"""
StockSense AI - Purchase Order Models
"""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import (
    String, DateTime, Integer, ForeignKey, Text, Numeric, Date, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PurchaseOrder(Base):
    """Purchase order header."""
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id"), nullable=False, index=True
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="DRAFT"
    )  # DRAFT, ORDERED, PARTIALLY_RECEIVED, RECEIVED, CANCELLED
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    supplier: Mapped["Supplier"] = relationship("Supplier", lazy="selectin")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan", lazy="selectin"
    )
    receipts: Mapped[list["PurchaseReceipt"]] = relationship(
        "PurchaseReceipt", back_populates="purchase_order", lazy="selectin"
    )


class PurchaseOrderItem(Base):
    """Line item on a purchase order."""
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False
    )
    ordered_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="items"
    )
    product: Mapped["Product"] = relationship("Product")


class PurchaseReceipt(Base):
    """Receipt event against a purchase order."""
    __tablename__ = "purchase_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="receipts", lazy="selectin"
    )
    items: Mapped[list["PurchaseReceiptItem"]] = relationship(
        "PurchaseReceiptItem", back_populates="receipt", cascade="all, delete-orphan", lazy="selectin"
    )


class PurchaseReceiptItem(Base):
    """Line item received in a purchase receipt."""
    __tablename__ = "purchase_receipt_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_receipt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_receipts.id"), nullable=False
    )
    purchase_order_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_order_items.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False
    )
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(100), nullable=True)
    manufacture_date: Mapped[date] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=True)
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inventory_batches.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    receipt: Mapped["PurchaseReceipt"] = relationship(
        "PurchaseReceipt", back_populates="items"
    )
    purchase_order_item: Mapped["PurchaseOrderItem"] = relationship("PurchaseOrderItem")
    product: Mapped["Product"] = relationship("Product")
