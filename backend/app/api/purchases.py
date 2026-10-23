"""
StockSense AI - Purchase Orders Router
"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.purchase_service import PurchaseService
from app.schemas.purchase import (
    PurchaseOrderCreate, PurchaseOrderUpdate,
    PurchaseOrderResponse, PurchaseOrderItemResponse,
    PurchaseOrderListResponse,
    ReceiptCreate, ReceiptResponse,
)

router = APIRouter(tags=["Purchase Orders"])


@router.get("/api/purchase-orders", response_model=PurchaseOrderListResponse)
@router.get("/api/purchases", response_model=PurchaseOrderListResponse)
async def list_purchase_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
    supplier_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List purchase orders with filters."""
    query = select(PurchaseOrder)

    if status_filter:
        query = query.where(PurchaseOrder.status == status_filter)
    if supplier_id:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(PurchaseOrder.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    orders = result.scalars().all()

    items = []
    for po in orders:
        supplier = await db.get(Supplier, po.supplier_id)

        # Load line items
        po_items_result = await db.execute(
            select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po.id)
        )
        po_items = po_items_result.scalars().all()

        item_responses = []
        for poi in po_items:
            product = await db.get(Product, poi.product_id)
            item_responses.append(PurchaseOrderItemResponse(
                id=poi.id, product_id=poi.product_id,
                product_name=product.name if product else None,
                ordered_quantity=poi.ordered_quantity,
                received_quantity=poi.received_quantity,
                remaining_quantity=poi.ordered_quantity - poi.received_quantity,
                unit_cost=poi.unit_cost, line_total=poi.line_total,
            ))

        items.append(PurchaseOrderResponse(
            id=po.id, po_number=po.po_number,
            supplier_id=po.supplier_id,
            supplier_name=supplier.name if supplier else None,
            order_date=po.order_date,
            expected_delivery_date=po.expected_delivery_date,
            status=po.status, total_amount=po.total_amount,
            notes=po.notes, items=item_responses,
            created_at=po.created_at, updated_at=po.updated_at,
        ))

    return PurchaseOrderListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/api/purchase-orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/purchases", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a draft purchase order."""
    try:
        po = await PurchaseService.create_purchase_order(
            db=db,
            supplier_id=data.supplier_id,
            items=data.items,
            order_date=data.order_date,
            expected_delivery_date=data.expected_delivery_date,
            notes=data.notes,
            created_by=current_user.id,
        )

        supplier = await db.get(Supplier, po.supplier_id)

        # Reload items
        po_items_result = await db.execute(
            select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po.id)
        )
        po_items = po_items_result.scalars().all()

        item_responses = []
        for poi in po_items:
            product = await db.get(Product, poi.product_id)
            item_responses.append(PurchaseOrderItemResponse(
                id=poi.id, product_id=poi.product_id,
                product_name=product.name if product else None,
                ordered_quantity=poi.ordered_quantity,
                received_quantity=poi.received_quantity,
                remaining_quantity=poi.ordered_quantity - poi.received_quantity,
                unit_cost=poi.unit_cost, line_total=poi.line_total,
            ))

        return PurchaseOrderResponse(
            id=po.id, po_number=po.po_number,
            supplier_id=po.supplier_id,
            supplier_name=supplier.name if supplier else None,
            order_date=po.order_date,
            expected_delivery_date=po.expected_delivery_date,
            status=po.status, total_amount=po.total_amount,
            notes=po.notes, items=item_responses,
            created_at=po.created_at, updated_at=po.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
@router.get("/api/purchases/{po_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a purchase order by ID."""
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    supplier = await db.get(Supplier, po.supplier_id)
    po_items_result = await db.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po.id)
    )
    po_items = po_items_result.scalars().all()

    item_responses = []
    for poi in po_items:
        product = await db.get(Product, poi.product_id)
        item_responses.append(PurchaseOrderItemResponse(
            id=poi.id, product_id=poi.product_id,
            product_name=product.name if product else None,
            ordered_quantity=poi.ordered_quantity,
            received_quantity=poi.received_quantity,
            remaining_quantity=poi.ordered_quantity - poi.received_quantity,
            unit_cost=poi.unit_cost, line_total=poi.line_total,
        ))

    return PurchaseOrderResponse(
        id=po.id, po_number=po.po_number,
        supplier_id=po.supplier_id,
        supplier_name=supplier.name if supplier else None,
        order_date=po.order_date,
        expected_delivery_date=po.expected_delivery_date,
        status=po.status, total_amount=po.total_amount,
        notes=po.notes, items=item_responses,
        created_at=po.created_at, updated_at=po.updated_at,
    )


@router.put("/api/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
@router.put("/api/purchases/{po_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    po_id: int,
    data: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a purchase order (only DRAFT orders)."""
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Can only update DRAFT orders")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(po, key, value)

    return await get_purchase_order(po_id, db, current_user)


@router.post("/api/purchase-orders/{po_id}/confirm", response_model=PurchaseOrderResponse)
@router.post("/api/purchases/{po_id}/confirm", response_model=PurchaseOrderResponse)
async def confirm_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm a draft purchase order."""
    try:
        po = await PurchaseService.confirm_order(db, po_id)
        await db.commit()
        return await get_purchase_order(po_id, db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/purchase-orders/{po_id}/receive", response_model=ReceiptResponse)
@router.post("/api/purchases/{po_id}/receive", response_model=ReceiptResponse)
async def receive_purchase_order(
    po_id: int,
    data: ReceiptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record receipt of goods against a purchase order."""
    try:
        receipt = await PurchaseService.receive_order(
            db=db,
            po_id=po_id,
            receipt_items=data.items,
            receipt_date=data.receipt_date,
            notes=data.notes,
            created_by=current_user.id,
        )
        await db.commit()
        return ReceiptResponse(
            id=receipt.id,
            purchase_order_id=receipt.purchase_order_id,
            receipt_number=receipt.receipt_number,
            receipt_date=receipt.receipt_date,
            notes=receipt.notes,
            created_at=receipt.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/purchase-orders/{po_id}/cancel", response_model=PurchaseOrderResponse)
@router.post("/api/purchases/{po_id}/cancel", response_model=PurchaseOrderResponse)
async def cancel_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a purchase order."""
    try:
        po = await PurchaseService.cancel_order(db, po_id)
        await db.commit()
        return await get_purchase_order(po_id, db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
