"""
StockSense AI - Purchase Order Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date


class PurchaseOrderItemCreate(BaseModel):
    product_id: int
    ordered_quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    order_date: Optional[date] = None  # defaults to today
    expected_delivery_date: Optional[date] = None
    items: List[PurchaseOrderItemCreate] = Field(..., min_length=1)
    notes: Optional[str] = None


class PurchaseOrderUpdate(BaseModel):
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None


class PurchaseOrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    ordered_quantity: Decimal
    received_quantity: Decimal
    remaining_quantity: Optional[Decimal] = None
    unit_cost: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    supplier_name: Optional[str] = None
    order_date: date
    expected_delivery_date: Optional[date]
    status: str
    total_amount: Decimal
    notes: Optional[str]
    items: List[PurchaseOrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PurchaseOrderListResponse(BaseModel):
    items: List[PurchaseOrderResponse]
    total: int
    page: int
    page_size: int


# Receipt schemas
class ReceiptItemCreate(BaseModel):
    purchase_order_item_id: int
    quantity_received: Decimal = Field(..., gt=0)
    unit_cost: Optional[Decimal] = None  # defaults to PO item cost
    batch_number: Optional[str] = None
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None


class ReceiptCreate(BaseModel):
    receipt_date: Optional[date] = None
    items: List[ReceiptItemCreate] = Field(..., min_length=1)
    notes: Optional[str] = None


class ReceiptResponse(BaseModel):
    id: int
    purchase_order_id: int
    receipt_number: str
    receipt_date: date
    notes: Optional[str]
    items: list = []
    created_at: datetime

    model_config = {"from_attributes": True}
