"""
StockSense AI - Supplier Schemas
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    contact_person: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    lead_time_days: int = Field(default=3, ge=0)
    min_order_quantity: Optional[Decimal] = Field(None, ge=0)
    min_order_value: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    is_active: bool = True


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    contact_person: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    lead_time_days: Optional[int] = Field(None, ge=0)
    min_order_quantity: Optional[Decimal] = Field(None, ge=0)
    min_order_value: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    contact_person: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    lead_time_days: int
    min_order_quantity: Optional[Decimal]
    min_order_value: Optional[Decimal]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    items: List[SupplierResponse]
    total: int
    page: int
    page_size: int
