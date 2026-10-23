"""
StockSense AI - Forecast, Reorder & Budget Router
"""

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.models.purchase import PurchaseOrder
from app.models.forecast import (
    ForecastRun, DailyForecast,
    ReorderRecommendation, BudgetPlan, BudgetPlanItem,
)
from app.models.inventory import InventoryBatch
from app.services.inventory_service import InventoryService
from app.forecasting.engine import forecast_product
from app.services.reorder_engine import ReorderEngine
from app.services.budget_optimizer import BudgetOptimizer
from app.schemas.forecast import (
    ForecastRunRequest, ForecastRunResponse, DailyForecastResponse,
    ReorderRecommendationResponse, ReorderListResponse,
    BudgetPlanCreate, BudgetPlanResponse, BudgetPlanItemResponse,
    ExpiryBatchResponse, ExpirySummaryResponse,
)

router = APIRouter(tags=["Forecasting & AI"])


# --- Forecast endpoints ---

@router.post("/api/forecast/run", response_model=ForecastRunResponse)
async def run_forecast(
    data: ForecastRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run demand forecasting for products."""
    today = date.today()
    now = datetime.now(timezone.utc)

    # Get products to forecast
    query = select(Product).where(Product.is_active == True)
    if data.product_ids:
        query = query.where(Product.id.in_(data.product_ids))
    result = await db.execute(query)
    products = result.scalars().all()

    if not products:
        raise HTTPException(status_code=400, detail="No active products found")

    # Create forecast run
    run = ForecastRun(
        run_date=now,
        horizon_days=data.horizon_days,
    )
    db.add(run)
    await db.flush()

    all_forecasts = []
    models_used = set()

    for product in products:
        # Get historical sales data
        sales_result = await db.execute(
            select(SaleItem.quantity, Sale.sale_date)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(
                SaleItem.product_id == product.id,
                Sale.status == "COMPLETED",
            )
            .order_by(Sale.sale_date)
        )
        sales_rows = sales_result.all()

        sales_data = [
            {"date": row.sale_date.date() if hasattr(row.sale_date, 'date') else row.sale_date,
             "quantity": float(row.quantity)}
            for row in sales_rows
        ]

        # Run forecast
        product_forecast = forecast_product(
            product_id=product.id,
            sales_data=sales_data,
            horizon=data.horizon_days,
            today=today,
        )
        models_used.add(product_forecast.model_used)

        # Store forecasts
        for fc in product_forecast.forecasts:
            daily = DailyForecast(
                forecast_run_id=run.id,
                product_id=product.id,
                forecast_date=fc["date"],
                predicted_demand=Decimal(str(fc["predicted_demand"])),
                lower_bound=Decimal(str(fc["lower_bound"])) if fc.get("lower_bound") is not None else None,
                upper_bound=Decimal(str(fc["upper_bound"])) if fc.get("upper_bound") is not None else None,
                model_used=product_forecast.model_used,
                confidence=product_forecast.confidence,
                mae=Decimal(str(product_forecast.mae)) if product_forecast.mae is not None else None,
                wape=Decimal(str(product_forecast.wape)) if product_forecast.wape is not None else None,
            )
            db.add(daily)
            all_forecasts.append(daily)

    run.model_used = ", ".join(sorted(models_used))
    run.notes = f"Forecasted {len(products)} products for {data.horizon_days} days"

    await db.flush()

    # Build response
    forecast_responses = []
    for fc in all_forecasts:
        product = await db.get(Product, fc.product_id)
        forecast_responses.append(DailyForecastResponse(
            product_id=fc.product_id,
            product_name=product.name if product else None,
            forecast_date=fc.forecast_date,
            predicted_demand=fc.predicted_demand,
            lower_bound=fc.lower_bound,
            upper_bound=fc.upper_bound,
            model_used=fc.model_used,
            confidence=fc.confidence,
            mae=fc.mae, wape=fc.wape,
        ))

    return ForecastRunResponse(
        id=run.id, run_date=run.run_date,
        horizon_days=run.horizon_days,
        model_used=run.model_used, notes=run.notes,
        daily_forecasts=forecast_responses,
        created_at=run.created_at,
    )


@router.get("/api/forecast/latest", response_model=ForecastRunResponse)
async def get_latest_forecast(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the latest forecast run results."""
    result = await db.execute(
        select(ForecastRun).order_by(ForecastRun.created_at.desc()).limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="No forecast runs found. Run a forecast first.")

    forecasts_result = await db.execute(
        select(DailyForecast).where(DailyForecast.forecast_run_id == run.id)
    )
    forecasts = forecasts_result.scalars().all()

    forecast_responses = []
    for fc in forecasts:
        product = await db.get(Product, fc.product_id)
        forecast_responses.append(DailyForecastResponse(
            product_id=fc.product_id,
            product_name=product.name if product else None,
            forecast_date=fc.forecast_date,
            predicted_demand=fc.predicted_demand,
            lower_bound=fc.lower_bound, upper_bound=fc.upper_bound,
            model_used=fc.model_used, confidence=fc.confidence,
            mae=fc.mae, wape=fc.wape,
        ))

    return ForecastRunResponse(
        id=run.id, run_date=run.run_date,
        horizon_days=run.horizon_days,
        model_used=run.model_used, notes=run.notes,
        daily_forecasts=forecast_responses,
        created_at=run.created_at,
    )


# --- Reorder endpoints ---

@router.post("/api/reorder/recalculate", response_model=ReorderListResponse)
async def recalculate_reorder(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recalculate reorder recommendations."""
    recommendations = await ReorderEngine.calculate_recommendations(db)

    items = []
    for rec in recommendations:
        product = await db.get(Product, rec.product_id)
        items.append(ReorderRecommendationResponse(
            id=rec.id, product_id=rec.product_id,
            product_name=product.name if product else None,
            sku=product.sku if product else None,
            unit=product.unit if product else None,
            run_date=rec.run_date,
            usable_stock=rec.usable_stock, incoming_stock=rec.incoming_stock,
            lead_time_demand=rec.lead_time_demand,
            safety_stock=rec.safety_stock,
            target_stock=rec.target_stock,
            inventory_position=rec.inventory_position,
            suggested_quantity=rec.suggested_quantity,
            estimated_cost=rec.estimated_cost,
            priority=rec.priority, explanation=rec.explanation,
            forecast_confidence=rec.forecast_confidence,
        ))

    return ReorderListResponse(
        items=items, total=len(items),
        run_date=items[0].run_date if items else None,
    )


@router.get("/api/reorder/recommendations", response_model=ReorderListResponse)
async def get_reorder_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get latest reorder recommendations."""
    # Get the latest run date
    result = await db.execute(
        select(ReorderRecommendation.run_date)
        .order_by(ReorderRecommendation.run_date.desc())
        .limit(1)
    )
    latest_date = result.scalar_one_or_none()

    if not latest_date:
        return ReorderListResponse(items=[], total=0)

    recs_result = await db.execute(
        select(ReorderRecommendation)
        .where(ReorderRecommendation.run_date == latest_date)
        .order_by(
            # URGENT first
            func.case(
                (ReorderRecommendation.priority == "URGENT", 0),
                (ReorderRecommendation.priority == "HIGH", 1),
                (ReorderRecommendation.priority == "MEDIUM", 2),
                else_=3,
            )
        )
    )
    recs = recs_result.scalars().all()

    items = []
    for rec in recs:
        product = await db.get(Product, rec.product_id)
        items.append(ReorderRecommendationResponse(
            id=rec.id, product_id=rec.product_id,
            product_name=product.name if product else None,
            sku=product.sku if product else None,
            unit=product.unit if product else None,
            run_date=rec.run_date,
            usable_stock=rec.usable_stock, incoming_stock=rec.incoming_stock,
            lead_time_demand=rec.lead_time_demand,
            safety_stock=rec.safety_stock,
            target_stock=rec.target_stock,
            inventory_position=rec.inventory_position,
            suggested_quantity=rec.suggested_quantity,
            estimated_cost=rec.estimated_cost,
            priority=rec.priority, explanation=rec.explanation,
            forecast_confidence=rec.forecast_confidence,
        ))

    return ReorderListResponse(items=items, total=len(items), run_date=latest_date)


# --- Budget plan endpoints ---

@router.post("/api/budget-plans", response_model=BudgetPlanResponse)
async def create_budget_plan(
    data: BudgetPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a budget-constrained purchase plan."""
    try:
        plan = await BudgetOptimizer.create_budget_plan(
            db=db,
            budget_amount=data.budget_amount,
            created_by=current_user.id,
        )

        # Load items
        items_result = await db.execute(
            select(BudgetPlanItem).where(BudgetPlanItem.budget_plan_id == plan.id)
        )
        plan_items = items_result.scalars().all()

        item_responses = []
        for pi in plan_items:
            product = await db.get(Product, pi.product_id)
            item_responses.append(BudgetPlanItemResponse(
                product_id=pi.product_id,
                product_name=product.name if product else None,
                suggested_quantity=pi.suggested_quantity,
                unit_cost=pi.unit_cost, line_cost=pi.line_cost,
                priority=pi.priority, included=pi.included,
                exclusion_reason=pi.exclusion_reason,
            ))

        return BudgetPlanResponse(
            id=plan.id, budget_amount=plan.budget_amount,
            total_allocated=plan.total_allocated,
            remaining_budget=plan.remaining_budget,
            items_included=plan.items_included,
            items_excluded=plan.items_excluded,
            notes=plan.notes, items=item_responses,
            created_at=plan.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/budget-plans/{plan_id}", response_model=BudgetPlanResponse)
async def get_budget_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a budget plan by ID."""
    plan = await db.get(BudgetPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Budget plan not found")

    items_result = await db.execute(
        select(BudgetPlanItem).where(BudgetPlanItem.budget_plan_id == plan.id)
    )
    plan_items = items_result.scalars().all()

    item_responses = []
    for pi in plan_items:
        product = await db.get(Product, pi.product_id)
        item_responses.append(BudgetPlanItemResponse(
            product_id=pi.product_id,
            product_name=product.name if product else None,
            suggested_quantity=pi.suggested_quantity,
            unit_cost=pi.unit_cost, line_cost=pi.line_cost,
            priority=pi.priority, included=pi.included,
            exclusion_reason=pi.exclusion_reason,
        ))

    return BudgetPlanResponse(
        id=plan.id, budget_amount=plan.budget_amount,
        total_allocated=plan.total_allocated,
        remaining_budget=plan.remaining_budget,
        items_included=plan.items_included,
        items_excluded=plan.items_excluded,
        notes=plan.notes, items=item_responses,
        created_at=plan.created_at,
    )


# --- Expiry endpoints ---

@router.get("/api/expiry/summary", response_model=ExpirySummaryResponse)
async def get_expiry_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get expiry summary across all batches."""
    today = date.today()

    result = await db.execute(
        select(InventoryBatch)
        .where(InventoryBatch.remaining_quantity > 0)
        .order_by(InventoryBatch.expiry_date.asc().nullslast())
    )
    batches = result.scalars().all()

    expired_count = 0
    expired_value = Decimal("0")
    within_7_count = 0
    within_7_value = Decimal("0")
    within_15_count = 0
    within_15_value = Decimal("0")
    within_30_count = 0
    within_30_value = Decimal("0")
    safe_count = 0
    safe_value = Decimal("0")
    no_expiry_count = 0

    batch_responses = []

    for batch in batches:
        product = await db.get(Product, batch.product_id)
        cost_at_risk = batch.remaining_quantity * batch.unit_cost

        if batch.expiry_date is None:
            category = "NO_EXPIRY"
            days_until = None
            no_expiry_count += 1
            recommended_action = None
        else:
            days_until = (batch.expiry_date - today).days
            if days_until <= 0:
                category = "EXPIRED"
                expired_count += 1
                expired_value += cost_at_risk
                recommended_action = "Remove from stock. This batch has expired."
            elif days_until <= 7:
                category = "WITHIN_7_DAYS"
                within_7_count += 1
                within_7_value += cost_at_risk
                recommended_action = f"Urgent: Expires in {days_until} days. Prioritize selling or discount."
            elif days_until <= 15:
                category = "WITHIN_15_DAYS"
                within_15_count += 1
                within_15_value += cost_at_risk
                recommended_action = f"Expiring soon ({days_until} days). Monitor sales velocity."
            elif days_until <= 30:
                category = "WITHIN_30_DAYS"
                within_30_count += 1
                within_30_value += cost_at_risk
                recommended_action = f"Expires in {days_until} days. Ensure adequate sales coverage."
            else:
                category = "SAFE"
                safe_count += 1
                safe_value += cost_at_risk
                recommended_action = None

        batch_responses.append(ExpiryBatchResponse(
            batch_id=batch.id,
            product_id=batch.product_id,
            product_name=product.name if product else "Unknown",
            sku=product.sku if product else "",
            batch_number=batch.batch_number,
            remaining_quantity=batch.remaining_quantity,
            unit_cost=batch.unit_cost,
            cost_at_risk=cost_at_risk,
            expiry_date=batch.expiry_date,
            days_until_expiry=days_until,
            expiry_category=category,
            recommended_action=recommended_action,
        ))

    return ExpirySummaryResponse(
        expired_count=expired_count, expired_value=expired_value,
        within_7_days_count=within_7_count, within_7_days_value=within_7_value,
        within_15_days_count=within_15_count, within_15_days_value=within_15_value,
        within_30_days_count=within_30_count, within_30_days_value=within_30_value,
        safe_count=safe_count, safe_value=safe_value,
        no_expiry_count=no_expiry_count,
        batches=batch_responses,
    )


@router.get("/api/expiry/batches")
async def get_expiry_batches(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get batches filtered by expiry category."""
    summary = await get_expiry_summary(db=db, current_user=current_user)
    if category:
        filtered = [b for b in summary.batches if b.expiry_category == category]
        return filtered
    return summary.batches


# --- Dashboard endpoint ---

@router.get("/api/dashboard/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard summary data."""
    today = date.today()
    now = datetime.now(timezone.utc)
    start_of_day = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

    # Active products
    active_result = await db.execute(
        select(func.count(Product.id)).where(Product.is_active == True)
    )
    active_products = active_result.scalar() or 0

    # Inventory value
    inv_summary = await InventoryService.get_inventory_summary(db)
    total_inventory_value = inv_summary["total_value"]
    low_stock_products = inv_summary["low_stock_count"]

    # Expiring batches
    expiry_7 = await db.execute(
        select(func.count(InventoryBatch.id))
        .where(
            InventoryBatch.remaining_quantity > 0,
            InventoryBatch.expiry_date.isnot(None),
            InventoryBatch.expiry_date > today,
            InventoryBatch.expiry_date <= today + __import__('datetime').timedelta(days=7),
        )
    )
    expiring_7 = expiry_7.scalar() or 0

    expiry_15 = await db.execute(
        select(func.count(InventoryBatch.id))
        .where(
            InventoryBatch.remaining_quantity > 0,
            InventoryBatch.expiry_date.isnot(None),
            InventoryBatch.expiry_date > today,
            InventoryBatch.expiry_date <= today + __import__('datetime').timedelta(days=15),
        )
    )
    expiring_15 = expiry_15.scalar() or 0

    expiry_30 = await db.execute(
        select(func.count(InventoryBatch.id))
        .where(
            InventoryBatch.remaining_quantity > 0,
            InventoryBatch.expiry_date.isnot(None),
            InventoryBatch.expiry_date > today,
            InventoryBatch.expiry_date <= today + __import__('datetime').timedelta(days=30),
        )
    )
    expiring_30 = expiry_30.scalar() or 0

    # Pending POs
    from app.models.purchase import PurchaseOrder
    pending_pos = await db.execute(
        select(func.count(PurchaseOrder.id))
        .where(PurchaseOrder.status.in_(["ORDERED", "PARTIALLY_RECEIVED"]))
    )
    pending_purchase_orders = pending_pos.scalar() or 0

    # Today's sales
    today_sales = await db.execute(
        select(
            func.coalesce(func.sum(Sale.total_amount), Decimal("0")),
            func.coalesce(func.count(Sale.id), 0),
        )
        .where(
            Sale.sale_date >= start_of_day,
            Sale.status == "COMPLETED",
        )
    )
    row = today_sales.one()
    today_sales_value = row[0] or Decimal("0")

    today_qty = await db.execute(
        select(func.coalesce(func.sum(SaleItem.quantity), Decimal("0")))
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(
            Sale.sale_date >= start_of_day,
            Sale.status == "COMPLETED",
        )
    )
    today_sales_quantity = today_qty.scalar() or Decimal("0")

    # Predicted shortages (from latest reorder recommendations)
    shortage_result = await db.execute(
        select(func.count(ReorderRecommendation.id))
        .where(
            ReorderRecommendation.suggested_quantity > 0,
            ReorderRecommendation.priority.in_(["URGENT", "HIGH"]),
        )
    )
    predicted_shortages = shortage_result.scalar() or 0

    return {
        "active_products": active_products,
        "total_inventory_value": float(total_inventory_value),
        "low_stock_products": low_stock_products,
        "predicted_shortages": predicted_shortages,
        "expiring_7_days": expiring_7,
        "expiring_15_days": expiring_15,
        "expiring_30_days": expiring_30,
        "pending_purchase_orders": pending_purchase_orders,
        "today_sales_quantity": float(today_sales_quantity),
        "today_sales_value": float(today_sales_value),
    }


class BudgetSimRequest(BaseModel):
    budget_amount: float


@router.get("/api/forecast/dashboard/stats")
async def get_forecast_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Real database statistics for frontend dashboard."""
    today = date.today()
    now = datetime.now(timezone.utc)
    start_of_day = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    start_of_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)

    # 1. Total products
    prod_res = await db.execute(select(func.count(Product.id)).where(Product.is_active == True))
    total_products = prod_res.scalar() or 0

    # 2. Total inventory value & low stock count
    inv_summary = await InventoryService.get_inventory_summary(db)
    total_inventory_value = float(inv_summary["total_value"])
    low_stock_count = inv_summary["low_stock_count"]

    # 3. Expiring soon (within 30 days)
    exp_res = await db.execute(
        select(func.count(InventoryBatch.id))
        .where(
            InventoryBatch.remaining_quantity > 0,
            InventoryBatch.expiry_date.isnot(None),
            InventoryBatch.expiry_date <= today + timedelta(days=30),
        )
    )
    expiring_soon_count = exp_res.scalar() or 0

    # 4. Today sales amount and count
    today_res = await db.execute(
        select(
            func.coalesce(func.sum(Sale.total_amount), Decimal("0")),
            func.count(Sale.id),
        ).where(
            Sale.sale_date >= start_of_day,
            Sale.status == "COMPLETED",
        )
    )
    today_row = today_res.one()
    today_sales_amount = float(today_row[0])
    today_sales_count = today_row[1]

    # 5. Monthly sales amount
    month_res = await db.execute(
        select(func.coalesce(func.sum(Sale.total_amount), Decimal("0"))).where(
            Sale.sale_date >= start_of_month,
            Sale.status == "COMPLETED",
        )
    )
    monthly_sales_amount = float(month_res.scalar() or 0)

    # 6. Open purchase orders count
    po_res = await db.execute(
        select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.status.in_(["ORDERED", "PARTIALLY_RECEIVED", "DRAFT"])
        )
    )
    open_purchase_orders_count = po_res.scalar() or 0

    # 7. Top selling products (from completed sales)
    top_res = await db.execute(
        select(
            SaleItem.product_id,
            func.sum(SaleItem.quantity).label("total_qty"),
            func.sum(SaleItem.line_total).label("total_rev"),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(Sale.status == "COMPLETED")
        .group_by(SaleItem.product_id)
        .order_by(func.sum(SaleItem.line_total).desc())
        .limit(5)
    )
    top_selling = []
    for row in top_res.all():
        p = await db.get(Product, row[0])
        top_selling.append({
            "product_id": row[0],
            "name": p.name if p else "Product",
            "quantity": float(row[1]),
            "revenue": float(row[2]),
        })

    # 8. Sales trend for last 7 days
    sales_trend = []
    for i in range(6, -1, -1):
        day_date = today - timedelta(days=i)
        day_start = datetime(day_date.year, day_date.month, day_date.day, tzinfo=timezone.utc)
        day_end = datetime(day_date.year, day_date.month, day_date.day, 23, 59, 59, tzinfo=timezone.utc)
        day_res = await db.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")),
                func.count(Sale.id),
            ).where(
                Sale.sale_date >= day_start,
                Sale.sale_date <= day_end,
                Sale.status == "COMPLETED",
            )
        )
        d_row = day_res.one()
        sales_trend.append({
            "date": day_date.strftime("%m/%d"),
            "sales": float(d_row[0]),
            "orders": d_row[1],
        })

    return {
        "total_products": total_products,
        "total_inventory_value": total_inventory_value,
        "low_stock_count": low_stock_count,
        "expiring_soon_count": expiring_soon_count,
        "today_sales_amount": today_sales_amount,
        "today_sales_count": today_sales_count,
        "monthly_sales_amount": monthly_sales_amount,
        "open_purchase_orders_count": open_purchase_orders_count,
        "top_selling_products": top_selling,
        "sales_trend": sales_trend,
    }


@router.get("/api/forecast/expiry/alerts")
async def get_expiry_alerts_endpoint(
    days_threshold: int = Query(30, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Expiry alerts matching frontend ExpiryAlert model."""
    today = date.today()
    threshold_date = today + timedelta(days=days_threshold)

    result = await db.execute(
        select(InventoryBatch)
        .where(
            InventoryBatch.remaining_quantity > 0,
            InventoryBatch.expiry_date.isnot(None),
            InventoryBatch.expiry_date <= threshold_date,
        )
        .order_by(InventoryBatch.expiry_date.asc())
    )
    batches = result.scalars().all()

    alerts = []
    for b in batches:
        product = await db.get(Product, b.product_id)
        if not product:
            continue
        days_until = (b.expiry_date - today).days
        if days_until <= 0:
            status_str = "EXPIRED"
        elif days_until <= 3:
            status_str = "CRITICAL"
        elif days_until <= 15:
            status_str = "WARNING"
        else:
            status_str = "ATTENTION"

        potential_loss = float(b.remaining_quantity * b.unit_cost)
        unit_val = product.unit.value if hasattr(product.unit, 'value') else str(product.unit)
        alerts.append({
            "product_id": b.product_id,
            "product_name": product.name,
            "sku": product.sku,
            "batch_id": b.id,
            "batch_number": b.batch_number or f"BAT-{b.id}",
            "remaining_quantity": float(b.remaining_quantity),
            "unit": unit_val,
            "expiry_date": b.expiry_date.isoformat(),
            "days_until_expiry": days_until,
            "purchase_cost": float(b.unit_cost),
            "potential_loss": potential_loss,
            "status": status_str,
        })
    return alerts


@router.post("/api/forecast/budget/plan")
async def simulate_budget_plan_endpoint(
    data: BudgetSimRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Simulate budget plan matching frontend format."""
    plan = await BudgetOptimizer.create_budget_plan(
        db=db,
        budget_amount=Decimal(str(data.budget_amount)),
        created_by=current_user.id,
    )
    items_result = await db.execute(
        select(BudgetPlanItem).where(BudgetPlanItem.budget_plan_id == plan.id)
    )
    plan_items = items_result.scalars().all()

    items = []
    for pi in plan_items:
        product = await db.get(Product, pi.product_id)
        items.append({
            "product_id": pi.product_id,
            "product_name": product.name if product else None,
            "sku": product.sku if product else "",
            "suggested_quantity": float(pi.suggested_quantity),
            "unit_cost": float(pi.unit_cost),
            "line_cost": float(pi.line_cost),
            "priority": pi.priority,
            "included": pi.included,
            "exclusion_reason": pi.exclusion_reason,
        })

    return {
        "id": plan.id,
        "budget_amount": float(plan.budget_amount),
        "total_allocated": float(plan.total_allocated),
        "remaining_budget": float(plan.remaining_budget),
        "items_included": plan.items_included,
        "items_excluded": plan.items_excluded,
        "items": items,
        "notes": plan.notes,
    }


# --- Reports endpoints ---

@router.get("/api/reports/sales")
async def sales_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sales history report."""
    query = (
        select(
            Sale.sale_date,
            Sale.sale_number,
            Sale.total_amount,
            Sale.status,
            SaleItem.product_id,
            SaleItem.quantity,
            SaleItem.unit_price,
            SaleItem.line_total,
        )
        .join(SaleItem, Sale.id == SaleItem.sale_id)
    )

    if start_date:
        query = query.where(Sale.sale_date >= datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc))
    if end_date:
        query = query.where(Sale.sale_date <= datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc))
    if product_id:
        query = query.where(SaleItem.product_id == product_id)

    query = query.order_by(Sale.sale_date.desc())
    result = await db.execute(query)
    rows = result.all()

    report = []
    for row in rows:
        product = await db.get(Product, row.product_id)
        report.append({
            "sale_date": row.sale_date.isoformat(),
            "sale_number": row.sale_number,
            "product_name": product.name if product else "Unknown",
            "quantity": float(row.quantity),
            "unit_price": float(row.unit_price),
            "line_total": float(row.line_total),
            "status": row.status,
        })

    return {"report": report, "total_records": len(report)}


@router.get("/api/reports/inventory")
async def inventory_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current inventory report."""
    summary = await InventoryService.get_inventory_summary(db)
    return summary


@router.get("/api/reports/purchases")
async def purchases_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Purchase history report."""
    from app.models.purchase import PurchaseOrder

    query = select(PurchaseOrder).order_by(PurchaseOrder.order_date.desc())

    if start_date:
        query = query.where(PurchaseOrder.order_date >= start_date)
    if end_date:
        query = query.where(PurchaseOrder.order_date <= end_date)

    result = await db.execute(query)
    orders = result.scalars().all()

    report = []
    for po in orders:
        supplier = await db.get(Supplier, po.supplier_id)
        report.append({
            "po_number": po.po_number,
            "supplier_name": supplier.name if supplier else "Unknown",
            "order_date": po.order_date.isoformat(),
            "status": po.status,
            "total_amount": float(po.total_amount),
        })

    return {"report": report, "total_records": len(report)}
