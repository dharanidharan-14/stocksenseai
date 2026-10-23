"""
StockSense AI - Forecasting & AI Planning Models
"""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import (
    String, Boolean, DateTime, Integer, ForeignKey, Text, Numeric, Date, Uuid, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ForecastRun(Base):
    """Metadata for each forecast execution."""
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    model_used: Mapped[str] = mapped_column(String(50), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    daily_forecasts: Mapped[list["DailyForecast"]] = relationship(
        "DailyForecast", back_populates="forecast_run", cascade="all, delete-orphan"
    )


class DailyForecast(Base):
    """Per-product daily demand prediction."""
    __tablename__ = "daily_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("forecast_runs.id"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_demand: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    lower_bound: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    upper_bound: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    model_used: Mapped[str] = mapped_column(String(50), nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    mae: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=True)
    wape: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    forecast_run: Mapped["ForecastRun"] = relationship(
        "ForecastRun", back_populates="daily_forecasts"
    )
    product: Mapped["Product"] = relationship("Product")


class ReorderRecommendation(Base):
    """Calculated reorder suggestion for a product."""
    __tablename__ = "reorder_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    run_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usable_stock: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    incoming_stock: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    lead_time_demand: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    target_stock: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    inventory_position: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    suggested_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=True)  # URGENT, HIGH, MEDIUM, LOW
    explanation: Mapped[str] = mapped_column(Text, nullable=True)
    forecast_confidence: Mapped[str] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product")


class BudgetPlan(Base):
    """Budget-constrained purchase plan."""
    __tablename__ = "budget_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_allocated: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    remaining_budget: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    items_included: Mapped[int] = mapped_column(Integer, default=0)
    items_excluded: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    items: Mapped[list["BudgetPlanItem"]] = relationship(
        "BudgetPlanItem", back_populates="budget_plan", cascade="all, delete-orphan"
    )


class BudgetPlanItem(Base):
    """Item within a budget plan."""
    __tablename__ = "budget_plan_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("budget_plans.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False
    )
    suggested_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=True)
    included: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exclusion_reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    budget_plan: Mapped["BudgetPlan"] = relationship("BudgetPlan", back_populates="items")
    product: Mapped["Product"] = relationship("Product")


class ImportJob(Base):
    """Tracking CSV import operations."""
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # PRODUCTS, SALES
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="PENDING"
    )  # PENDING, PROCESSING, COMPLETED, FAILED
    total_rows: Mapped[int] = mapped_column(Integer, nullable=True)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=True)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=True)
    errors: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
