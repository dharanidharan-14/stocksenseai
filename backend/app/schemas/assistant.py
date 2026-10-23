"""
StockSense AI - Voice Assistant Schemas
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from decimal import Decimal
from datetime import date


class AssistantCommandRequest(BaseModel):
    text: str = Field("", max_length=2000)
    confirmed: bool = Field(False)
    session_id: Optional[str] = Field(None)
    action_payload: Optional[Dict[str, Any]] = Field(None)


class ProductMatch(BaseModel):
    product_id: int
    product_name: str
    sku: str
    unit: str


class StockInfo(BaseModel):
    product_id: int
    product_name: str
    sku: str
    unit: str
    usable_stock: Decimal
    total_stock: Decimal
    reorder_threshold: Decimal
    status: str


class BatchInfo(BaseModel):
    batch_number: Optional[str]
    product_id: int
    product_name: str
    remaining_quantity: Decimal
    unit: str
    expiry_date: Optional[date]
    days_until_expiry: Optional[int]
    status: str


class SaleSummaryData(BaseModel):
    total_sales: Decimal
    total_transactions: int
    date_range: str
    top_products: List[Dict[str, Any]] = []


class ReorderItem(BaseModel):
    product_id: int
    product_name: str
    sku: str
    unit: str
    current_stock: Decimal
    suggested_quantity: Decimal
    estimated_cost: Decimal
    reason: str
    priority: str


class AssistantResponse(BaseModel):
    intent: str
    speech_text: str
    display_text: str
    data: Optional[Any] = None
    requires_confirmation: bool = False
    action_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    suggestions: List[str] = []
