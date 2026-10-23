"""
StockSense AI - Sales Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)


class SaleCreate(BaseModel):
    sale_date: Optional[datetime] = None  # defaults to now
    items: List[SaleItemCreate] = Field(..., min_length=1)
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class SaleItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class SaleResponse(BaseModel):
    id: int
    sale_number: str
    sale_date: datetime
    total_amount: Decimal
    total_items: int
    reference_number: Optional[str]
    status: str
    notes: Optional[str]
    is_historical_import: bool
    items: List[SaleItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class SaleListResponse(BaseModel):
    items: List[SaleResponse]
    total: int
    page: int
    page_size: int
