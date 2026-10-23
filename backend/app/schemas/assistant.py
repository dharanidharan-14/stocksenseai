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


class GeminiParsedIntent(BaseModel):
    """Structured LLM intent output validated by Pydantic."""
    intent: str = Field(
        ...,
        description=(
            "Primary intent category. MUST be one of: "
            "CHECK_STOCK, CHECK_LOW_STOCK, CHECK_OUT_OF_STOCK, CHECK_EXPIRY, "
            "SALES_INFO, AI_RECOMMENDATION, RECEIVE_STOCK, RECORD_SALE, "
            "RECORD_DAMAGE, INVENTORY_CORRECTION, CONFIRMATION, CANCELLATION, "
            "CORRECTION, CLARIFICATION, UNKNOWN"
        )
    )
    product_raw: Optional[str] = Field(None, description="Raw product name or colloquial mention in speech, e.g. 'thakkali', 'tomato', 'aata', 'milk'")
    product_normalized: Optional[str] = Field(None, description="Canonical normalized English name, e.g. 'Tomato', 'Milk', 'Wheat Flour', 'Basmati Rice'")
    quantity: Optional[float] = Field(None, description="Explicit quantity mentioned e.g. 2, 5, 10.5")
    unit: Optional[str] = Field(None, description="Unit mentioned: packet, kg, piece, litre, bottle, box, etc.")
    time_frame: Optional[str] = Field(None, description="Time reference: 'today', 'tomorrow', 'this_week', '7_days', 'expired', or specific date")
    budget: Optional[float] = Field(None, description="Rupee purchase budget if mentioned e.g. 2000")
    cost_per_unit: Optional[float] = Field(None, description="Unit wholesale cost or selling price if specified")
    notes: Optional[str] = Field(None, description="Any extra notes or contextual reference")
    language_type: str = Field("English", description="Detected language: 'English', 'Tamil', 'Tanglish', or 'Local Slang'")
    spoken_reply_english: str = Field("", description="Clear concise spoken reply in English")
    spoken_reply_tamil: str = Field("", description="Natural colloquial spoken reply in Tamil or Tanglish")
    is_confirmation: bool = Field(False, description="True if user is confirming e.g. 'aama', 'yes', 'confirm', 'sari', 'proceed'")
    is_cancellation: bool = Field(False, description="True if user is cancelling e.g. 'cancel', 'vendaam', 'stop', 'cancel pannidu'")
    is_correction: bool = Field(False, description="True if user is correcting previous proposal e.g. 'illa, 5 illa 3 packet'")
    clarification_question: Optional[str] = Field(None, description="Clarifying question if critical info is missing")

