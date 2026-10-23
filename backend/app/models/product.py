"""
StockSense AI - Product & Category Models
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Text, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    products: Mapped[list["Product"]] = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # packet, piece, kg, g, litre, ml, bottle, box
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    preferred_supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id"), nullable=True
    )
    supplier_lead_time_days: Mapped[int] = mapped_column(Integer, default=3)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    reorder_threshold: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    shelf_life_days: Mapped[int] = mapped_column(Integer, nullable=True)  # NULL = non-perishable
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    preferred_supplier: Mapped["Supplier"] = relationship(
        "Supplier", foreign_keys=[preferred_supplier_id]
    )
    batches: Mapped[list["InventoryBatch"]] = relationship(
        "InventoryBatch", back_populates="product"
    )
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="product"
    )

    __table_args__ = (
        Index("ix_products_category_active", "category_id", "is_active"),
    )
