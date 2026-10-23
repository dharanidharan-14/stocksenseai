"""
StockSense AI - Product & Category Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from enum import Enum


class UnitEnum(str, Enum):
    PACKET = "packet"
    PIECE = "piece"
    KG = "kg"
    G = "g"
    LITRE = "litre"
    ML = "ml"
    BOTTLE = "bottle"
    BOX = "box"


# Category schemas
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# Product schemas
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: str = Field(..., min_length=1, max_length=50)
    category_id: Optional[int] = None
    unit: UnitEnum
    purchase_cost: Decimal = Field(..., ge=0, decimal_places=2)
    selling_price: Decimal = Field(..., ge=0, decimal_places=2)
    preferred_supplier_id: Optional[int] = None
    supplier_lead_time_days: int = Field(default=3, ge=0)
    safety_stock: Decimal = Field(default=Decimal("0"), ge=0)
    reorder_threshold: Decimal = Field(default=Decimal("0"), ge=0)
    shelf_life_days: Optional[int] = Field(None, ge=1)
    is_active: bool = True

    @field_validator("selling_price")
    @classmethod
    def selling_price_positive(cls, v, info):
        if v <= 0:
            raise ValueError("Selling price must be greater than 0")
        return v


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    sku: Optional[str] = Field(None, min_length=1, max_length=50)
    category_id: Optional[int] = None
    unit: Optional[UnitEnum] = None
    purchase_cost: Optional[Decimal] = Field(None, ge=0)
    selling_price: Optional[Decimal] = Field(None, ge=0)
    preferred_supplier_id: Optional[int] = None
    supplier_lead_time_days: Optional[int] = Field(None, ge=0)
    safety_stock: Optional[Decimal] = Field(None, ge=0)
    reorder_threshold: Optional[Decimal] = Field(None, ge=0)
    shelf_life_days: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    sku: str
    category_id: Optional[int]
    category_name: Optional[str] = None
    unit: str
    purchase_cost: Decimal
    selling_price: Decimal
    preferred_supplier_id: Optional[int]
    supplier_name: Optional[str] = None
    supplier_lead_time_days: int
    safety_stock: Decimal
    reorder_threshold: Decimal
    shelf_life_days: Optional[int]
    is_active: bool
    current_stock: Optional[Decimal] = None
    usable_stock: Optional[Decimal] = None
    total_stock: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
