"""
StockSense AI - Inventory Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date


class BatchResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    batch_number: Optional[str]
    received_quantity: Decimal
    remaining_quantity: Decimal
    unit_cost: Decimal
    manufacture_date: Optional[date]
    expiry_date: Optional[date]
    receipt_reference: Optional[str]
    source_type: str
    created_at: datetime
    days_until_expiry: Optional[int] = None
    expiry_status: Optional[str] = None

    model_config = {"from_attributes": True}


class StockReceiptCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)
    batch_number: Optional[str] = None
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None
    receipt_reference: Optional[str] = None
    notes: Optional[str] = None


class StockAdjustmentCreate(BaseModel):
    product_id: int
    batch_id: Optional[int] = None
    adjustment_type: str = Field(..., pattern="^(ADJUSTMENT|DAMAGE|CORRECTION|OPENING)$")
    quantity: Decimal  # positive = add, negative = remove
    notes: Optional[str] = None


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    batch_id: Optional[int]
    movement_type: str
    quantity: Decimal
    reference_type: Optional[str]
    reference_id: Optional[int]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class InventorySummaryItem(BaseModel):
    product_id: int
    product_name: str
    sku: str
    unit: str
    total_stock: Decimal
    usable_stock: Decimal
    expired_stock: Decimal
    total_value: Decimal
    reorder_threshold: Decimal
    is_low_stock: bool
    batch_count: int


class InventorySummaryResponse(BaseModel):
    items: List[InventorySummaryItem]
    total_products: int
    total_value: Decimal
    low_stock_count: int
    out_of_stock_count: int


class BatchListResponse(BaseModel):
    items: List[BatchResponse]
    total: int
    page: int
    page_size: int


class MovementListResponse(BaseModel):
    items: List[StockMovementResponse]
    total: int
    page: int
    page_size: int
