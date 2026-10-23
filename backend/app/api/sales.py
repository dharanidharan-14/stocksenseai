"""
StockSense AI - Sales Router
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.sale import Sale, SaleItem
from app.models.product import Product
from app.services.sales_service import SalesService
from app.schemas.sale import (
    SaleCreate, SaleResponse, SaleItemResponse, SaleListResponse,
)

router = APIRouter(prefix="/api/sales", tags=["Sales"])


@router.get("", response_model=SaleListResponse)
async def list_sales(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sales with filters and pagination."""
    sales, total = await SalesService.get_sales(
        db, page=page, page_size=page_size,
        status=status_filter, start_date=start_date, end_date=end_date,
    )

    items = []
    for sale in sales:
        # Load items
        items_result = await db.execute(
            select(SaleItem).where(SaleItem.sale_id == sale.id)
        )
        sale_items = items_result.scalars().all()

        sale_item_responses = []
        for si in sale_items:
            product = await db.get(Product, si.product_id)
            sale_item_responses.append(SaleItemResponse(
                id=si.id, product_id=si.product_id,
                product_name=product.name if product else None,
                quantity=si.quantity, unit_price=si.unit_price,
                line_total=si.line_total,
            ))

        items.append(SaleResponse(
            id=sale.id, sale_number=sale.sale_number,
            sale_date=sale.sale_date, total_amount=sale.total_amount,
            total_items=sale.total_items,
            reference_number=sale.reference_number,
            status=sale.status, notes=sale.notes,
            is_historical_import=sale.is_historical_import,
            items=sale_item_responses,
            created_at=sale.created_at,
        ))

    return SaleListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
async def create_sale(
    data: SaleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a sale. Deducts stock using FEFO."""
    try:
        sale = await SalesService.create_sale(
            db=db,
            items=data.items,
            sale_date=data.sale_date,
            reference_number=data.reference_number,
            notes=data.notes,
            created_by=current_user.id,
        )

        # Build response
        items_result = await db.execute(
            select(SaleItem).where(SaleItem.sale_id == sale.id)
        )
        sale_items = items_result.scalars().all()

        sale_item_responses = []
        for si in sale_items:
            product = await db.get(Product, si.product_id)
            sale_item_responses.append(SaleItemResponse(
                id=si.id, product_id=si.product_id,
                product_name=product.name if product else None,
                quantity=si.quantity, unit_price=si.unit_price,
                line_total=si.line_total,
            ))

        return SaleResponse(
            id=sale.id, sale_number=sale.sale_number,
            sale_date=sale.sale_date, total_amount=sale.total_amount,
            total_items=sale.total_items,
            reference_number=sale.reference_number,
            status=sale.status, notes=sale.notes,
            is_historical_import=sale.is_historical_import,
            items=sale_item_responses,
            created_at=sale.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a sale by ID."""
    sale = await db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    items_result = await db.execute(
        select(SaleItem).where(SaleItem.sale_id == sale.id)
    )
    sale_items = items_result.scalars().all()

    sale_item_responses = []
    for si in sale_items:
        product = await db.get(Product, si.product_id)
        sale_item_responses.append(SaleItemResponse(
            id=si.id, product_id=si.product_id,
            product_name=product.name if product else None,
            quantity=si.quantity, unit_price=si.unit_price,
            line_total=si.line_total,
        ))

    return SaleResponse(
        id=sale.id, sale_number=sale.sale_number,
        sale_date=sale.sale_date, total_amount=sale.total_amount,
        total_items=sale.total_items,
        reference_number=sale.reference_number,
        status=sale.status, notes=sale.notes,
        is_historical_import=sale.is_historical_import,
        items=sale_item_responses,
        created_at=sale.created_at,
    )


@router.post("/{sale_id}/cancel", response_model=SaleResponse)
async def cancel_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a sale and reverse stock movements."""
    try:
        sale = await SalesService.cancel_sale(db, sale_id)
        return SaleResponse(
            id=sale.id, sale_number=sale.sale_number,
            sale_date=sale.sale_date, total_amount=sale.total_amount,
            total_items=sale.total_items,
            reference_number=sale.reference_number,
            status=sale.status, notes=sale.notes,
            is_historical_import=sale.is_historical_import,
            created_at=sale.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
