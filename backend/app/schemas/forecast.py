"""
StockSense AI - Forecast & AI Planning Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date


class ForecastRunRequest(BaseModel):
    horizon_days: int = Field(default=7, ge=1, le=90)
    product_ids: Optional[List[int]] = None  # None = all active products


class DailyForecastResponse(BaseModel):
    product_id: int
    product_name: Optional[str] = None
    forecast_date: date
    predicted_demand: Decimal
    lower_bound: Optional[Decimal]
    upper_bound: Optional[Decimal]
    model_used: Optional[str]
    confidence: Optional[str]
    mae: Optional[Decimal]
    wape: Optional[Decimal]

    model_config = {"from_attributes": True}


class ForecastRunResponse(BaseModel):
    id: int
    run_date: datetime
    horizon_days: int
    model_used: Optional[str]
    notes: Optional[str]
    daily_forecasts: List[DailyForecastResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ReorderRecommendationResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    sku: Optional[str] = None
    unit: Optional[str] = None
    run_date: datetime
    usable_stock: Optional[Decimal]
    incoming_stock: Optional[Decimal]
    lead_time_demand: Optional[Decimal]
    safety_stock: Optional[Decimal]
    target_stock: Optional[Decimal]
    inventory_position: Optional[Decimal]
    suggested_quantity: Optional[Decimal]
    estimated_cost: Optional[Decimal]
    priority: Optional[str]
    explanation: Optional[str]
    forecast_confidence: Optional[str]

    model_config = {"from_attributes": True}


class ReorderListResponse(BaseModel):
    items: List[ReorderRecommendationResponse]
    total: int
    run_date: Optional[datetime] = None


class BudgetPlanCreate(BaseModel):
    budget_amount: Decimal = Field(..., gt=0)


class BudgetPlanItemResponse(BaseModel):
    product_id: int
    product_name: Optional[str] = None
    suggested_quantity: Decimal
    unit_cost: Decimal
    line_cost: Decimal
    priority: Optional[str]
    included: bool
    exclusion_reason: Optional[str]

    model_config = {"from_attributes": True}


class BudgetPlanResponse(BaseModel):
    id: int
    budget_amount: Decimal
    total_allocated: Decimal
    remaining_budget: Decimal
    items_included: int
    items_excluded: int
    notes: Optional[str]
    items: List[BudgetPlanItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# Expiry schemas
class ExpiryBatchResponse(BaseModel):
    batch_id: int
    product_id: int
    product_name: str
    sku: str
    batch_number: Optional[str]
    remaining_quantity: Decimal
    unit_cost: Decimal
    cost_at_risk: Decimal
    expiry_date: Optional[date]
    days_until_expiry: Optional[int]
    expiry_category: str  # EXPIRED, WITHIN_7_DAYS, WITHIN_15_DAYS, WITHIN_30_DAYS, SAFE, NO_EXPIRY
    recommended_action: Optional[str]
    can_sell_before_expiry: Optional[bool] = None

    model_config = {"from_attributes": True}


class ExpirySummaryResponse(BaseModel):
    expired_count: int
    expired_value: Decimal
    within_7_days_count: int
    within_7_days_value: Decimal
    within_15_days_count: int
    within_15_days_value: Decimal
    within_30_days_count: int
    within_30_days_value: Decimal
    safe_count: int
    safe_value: Decimal
    no_expiry_count: int
    batches: List[ExpiryBatchResponse] = []


# Dashboard schemas
class DashboardSummaryResponse(BaseModel):
    active_products: int
    total_inventory_value: Decimal
    low_stock_products: int
    predicted_shortages: int
    expiring_7_days: int
    expiring_15_days: int
    expiring_30_days: int
    pending_purchase_orders: int
    today_sales_quantity: Decimal
    today_sales_value: Decimal
    recommended_spend: Optional[Decimal] = None
    available_budget: Optional[Decimal] = None
