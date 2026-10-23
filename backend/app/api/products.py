"""
StockSense AI - Products Router
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.product import Product, Category
from app.models.supplier import Supplier
from app.services.inventory_service import InventoryService
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse,
    ProductListResponse, CategoryCreate, CategoryResponse,
)

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    sort_by: Optional[str] = "name",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List products with filtering, search, and pagination."""
    query = select(Product)

    if search:
        query = query.where(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
            )
        )
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    sort_map = {
        "name": Product.name,
        "sku": Product.sku,
        "purchase_cost": Product.purchase_cost,
        "selling_price": Product.selling_price,
        "created_at": Product.created_at,
    }
    sort_col = sort_map.get(sort_by, Product.name)
    query = query.order_by(sort_col)

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.scalars().all()

    # Build response with stock info
    items = []
    for p in products:
        stock = await InventoryService.get_usable_stock(db, p.id)
        cat_name = None
        if p.category_id:
            cat = await db.get(Category, p.category_id)
            cat_name = cat.name if cat else None

        sup_name = None
        if p.preferred_supplier_id:
            sup = await db.get(Supplier, p.preferred_supplier_id)
            sup_name = sup.name if sup else None

        items.append(ProductResponse(
            id=p.id, name=p.name, sku=p.sku,
            category_id=p.category_id, category_name=cat_name,
            unit=p.unit, purchase_cost=p.purchase_cost,
            selling_price=p.selling_price,
            preferred_supplier_id=p.preferred_supplier_id,
            supplier_name=sup_name,
            supplier_lead_time_days=p.supplier_lead_time_days,
            safety_stock=p.safety_stock, reorder_threshold=p.reorder_threshold,
            shelf_life_days=p.shelf_life_days, is_active=p.is_active,
            current_stock=stock,
            usable_stock=stock,
            total_stock=stock,
            created_at=p.created_at, updated_at=p.updated_at,
        ))

    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new product."""
    # Check SKU uniqueness
    existing = await db.execute(select(Product).where(Product.sku == data.sku))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"SKU '{data.sku}' already exists")

    # Validate category
    if data.category_id:
        cat = await db.get(Category, data.category_id)
        if not cat:
            raise HTTPException(status_code=400, detail="Invalid category ID")

    # Validate supplier
    if data.preferred_supplier_id:
        sup = await db.get(Supplier, data.preferred_supplier_id)
        if not sup:
            raise HTTPException(status_code=400, detail="Invalid supplier ID")

    product = Product(**data.model_dump())
    db.add(product)
    await db.flush()

    return ProductResponse(
        id=product.id, name=product.name, sku=product.sku,
        category_id=product.category_id, unit=product.unit,
        purchase_cost=product.purchase_cost, selling_price=product.selling_price,
        preferred_supplier_id=product.preferred_supplier_id,
        supplier_lead_time_days=product.supplier_lead_time_days,
        safety_stock=product.safety_stock, reorder_threshold=product.reorder_threshold,
        shelf_life_days=product.shelf_life_days, is_active=product.is_active,
        current_stock=0,
        created_at=product.created_at, updated_at=product.updated_at,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a product by ID."""
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    stock = await InventoryService.get_usable_stock(db, product.id)

    cat_name = None
    if product.category_id:
        cat = await db.get(Category, product.category_id)
        cat_name = cat.name if cat else None

    sup_name = None
    if product.preferred_supplier_id:
        sup = await db.get(Supplier, product.preferred_supplier_id)
        sup_name = sup.name if sup else None

    return ProductResponse(
        id=product.id, name=product.name, sku=product.sku,
        category_id=product.category_id, category_name=cat_name,
        unit=product.unit, purchase_cost=product.purchase_cost,
        selling_price=product.selling_price,
        preferred_supplier_id=product.preferred_supplier_id,
        supplier_name=sup_name,
        supplier_lead_time_days=product.supplier_lead_time_days,
        safety_stock=product.safety_stock, reorder_threshold=product.reorder_threshold,
        shelf_life_days=product.shelf_life_days, is_active=product.is_active,
        current_stock=stock,
        usable_stock=stock,
        total_stock=stock,
        created_at=product.created_at, updated_at=product.updated_at,
    )


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a product."""
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)

    # Check SKU uniqueness if updating
    if "sku" in update_data:
        existing = await db.execute(
            select(Product).where(Product.sku == update_data["sku"], Product.id != product_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"SKU '{update_data['sku']}' already exists")

    for key, value in update_data.items():
        setattr(product, key, value)

    stock = await InventoryService.get_usable_stock(db, product.id)

    return ProductResponse(
        id=product.id, name=product.name, sku=product.sku,
        category_id=product.category_id, unit=product.unit,
        purchase_cost=product.purchase_cost, selling_price=product.selling_price,
        preferred_supplier_id=product.preferred_supplier_id,
        supplier_lead_time_days=product.supplier_lead_time_days,
        safety_stock=product.safety_stock, reorder_threshold=product.reorder_threshold,
        shelf_life_days=product.shelf_life_days, is_active=product.is_active,
        current_stock=stock,
        usable_stock=stock,
        total_stock=stock,
        created_at=product.created_at, updated_at=product.updated_at,
    )


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a product (mark as inactive)."""
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = False


# Category endpoints
@router.get("/categories/list", response_model=list[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all product categories."""
    result = await db.execute(select(Category).order_by(Category.name))
    categories = result.scalars().all()
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a product category."""
    existing = await db.execute(select(Category).where(Category.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Category '{data.name}' already exists")

    category = Category(**data.model_dump())
    db.add(category)
    await db.flush()
    return CategoryResponse.model_validate(category)
