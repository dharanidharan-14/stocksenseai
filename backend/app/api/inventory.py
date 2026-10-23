"""
StockSense AI - Inventory Router
"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.inventory import InventoryBatch, StockMovement
from app.models.product import Product
from app.services.inventory_service import InventoryService
from app.schemas.inventory import (
    StockReceiptCreate, StockAdjustmentCreate,
    BatchResponse, StockMovementResponse,
    InventorySummaryResponse, InventorySummaryItem,
    BatchListResponse, MovementListResponse,
)

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


@router.get("/summary", response_model=InventorySummaryResponse)
async def get_inventory_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get inventory summary across all active products."""
    summary = await InventoryService.get_inventory_summary(db)
    return InventorySummaryResponse(
        items=[InventorySummaryItem(**item) for item in summary["items"]],
        total_products=summary["total_products"],
        total_value=summary["total_value"],
        low_stock_count=summary["low_stock_count"],
        out_of_stock_count=summary["out_of_stock_count"],
    )


@router.get("/batches", response_model=BatchListResponse)
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: Optional[int] = None,
    has_stock: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List inventory batches with filtering."""
    query = select(InventoryBatch)

    if product_id:
        query = query.where(InventoryBatch.product_id == product_id)
    if has_stock is True:
        query = query.where(InventoryBatch.remaining_quantity > 0)
    elif has_stock is False:
        query = query.where(InventoryBatch.remaining_quantity <= 0)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(InventoryBatch.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    batches = result.scalars().all()

    today = date.today()
    items = []
    for b in batches:
        product = await db.get(Product, b.product_id)
        days_until = None
        expiry_status = None
        if b.expiry_date:
            days_until = (b.expiry_date - today).days
            if days_until <= 0:
                expiry_status = "EXPIRED"
            elif days_until <= 7:
                expiry_status = "WITHIN_7_DAYS"
            elif days_until <= 15:
                expiry_status = "WITHIN_15_DAYS"
            elif days_until <= 30:
                expiry_status = "WITHIN_30_DAYS"
            else:
                expiry_status = "SAFE"
        else:
            expiry_status = "NO_EXPIRY"

        items.append(BatchResponse(
            id=b.id, product_id=b.product_id,
            product_name=product.name if product else None,
            batch_number=b.batch_number,
            received_quantity=b.received_quantity,
            remaining_quantity=b.remaining_quantity,
            unit_cost=b.unit_cost,
            manufacture_date=b.manufacture_date,
            expiry_date=b.expiry_date,
            receipt_reference=b.receipt_reference,
            source_type=b.source_type,
            created_at=b.created_at,
            days_until_expiry=days_until,
            expiry_status=expiry_status,
        ))

    return BatchListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/batches/{batch_id}", response_model=BatchResponse)
async def get_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single batch by ID."""
    b = await db.get(InventoryBatch, batch_id)
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found")
    product = await db.get(Product, b.product_id)
    today = date.today()
    days_until = None
    expiry_status = None
    if b.expiry_date:
        days_until = (b.expiry_date - today).days
        if days_until <= 0:
            expiry_status = "EXPIRED"
        elif days_until <= 7:
            expiry_status = "WITHIN_7_DAYS"
        elif days_until <= 15:
            expiry_status = "WITHIN_15_DAYS"
        elif days_until <= 30:
            expiry_status = "WITHIN_30_DAYS"
        else:
            expiry_status = "SAFE"
    else:
        expiry_status = "NO_EXPIRY"

    return BatchResponse(
        id=b.id,
        product_id=b.product_id,
        product_name=product.name if product else None,
        batch_number=b.batch_number,
        received_quantity=b.received_quantity,
        remaining_quantity=b.remaining_quantity,
        unit_cost=b.unit_cost,
        manufacture_date=b.manufacture_date,
        expiry_date=b.expiry_date,
        receipt_reference=b.receipt_reference,
        source_type=b.source_type,
        created_at=b.created_at,
        days_until_expiry=days_until,
        expiry_status=expiry_status,
    )


@router.get("/movements", response_model=MovementListResponse)
async def list_movements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List stock movements with filtering."""
    query = select(StockMovement)

    if product_id:
        query = query.where(StockMovement.product_id == product_id)
    if movement_type:
        query = query.where(StockMovement.movement_type == movement_type)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(StockMovement.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    movements = result.scalars().all()

    items = []
    for m in movements:
        product = await db.get(Product, m.product_id)
        items.append(StockMovementResponse(
            id=m.id, product_id=m.product_id,
            product_name=product.name if product else None,
            batch_id=m.batch_id, movement_type=m.movement_type,
            quantity=m.quantity, reference_type=m.reference_type,
            reference_id=m.reference_id, notes=m.notes,
            created_at=m.created_at,
        ))

    return MovementListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/receipts", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_stock_receipt(
    data: StockReceiptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a direct stock receipt (opening stock or adjustment)."""
    try:
        batch, movement = await InventoryService.create_stock_receipt(
            db=db,
            product_id=data.product_id,
            quantity=data.quantity,
            unit_cost=data.unit_cost,
            batch_number=data.batch_number,
            manufacture_date=data.manufacture_date,
            expiry_date=data.expiry_date,
            receipt_reference=data.receipt_reference,
            source_type="OPENING",
            notes=data.notes,
        )
        product = await db.get(Product, data.product_id)
        return BatchResponse(
            id=batch.id, product_id=batch.product_id,
            product_name=product.name if product else None,
            batch_number=batch.batch_number,
            received_quantity=batch.received_quantity,
            remaining_quantity=batch.remaining_quantity,
            unit_cost=batch.unit_cost,
            manufacture_date=batch.manufacture_date,
            expiry_date=batch.expiry_date,
            receipt_reference=batch.receipt_reference,
            source_type=batch.source_type,
            created_at=batch.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/adjustments", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
async def create_stock_adjustment(
    data: StockAdjustmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a stock adjustment (damage, correction, etc.)."""
    try:
        movement = await InventoryService.create_adjustment(
            db=db,
            product_id=data.product_id,
            adjustment_type=data.adjustment_type,
            quantity=data.quantity,
            batch_id=data.batch_id,
            notes=data.notes,
        )
        product = await db.get(Product, data.product_id)
        return StockMovementResponse(
            id=movement.id, product_id=movement.product_id,
            product_name=product.name if product else None,
            batch_id=movement.batch_id,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            reference_type=movement.reference_type,
            reference_id=movement.reference_id,
            notes=movement.notes,
            created_at=movement.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
