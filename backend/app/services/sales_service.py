"""
StockSense AI - Sales Service

Handles sale recording with FEFO stock consumption,
sale cancellation with compensating movements.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sale import Sale, SaleItem
from app.models.product import Product
from app.services.inventory_service import InventoryService


class SalesService:
    """Handles sale transactions with stock deduction."""

    @staticmethod
    async def generate_sale_number(db: AsyncSession) -> str:
        """Generate a unique sale number."""
        result = await db.execute(
            select(func.count(Sale.id))
        )
        count = result.scalar() or 0
        now = datetime.now(timezone.utc)
        return f"SL-{now.strftime('%Y%m%d')}-{count + 1:04d}"

    @staticmethod
    async def create_sale(
        db: AsyncSession,
        items: list,
        sale_date: Optional[datetime] = None,
        reference_number: Optional[str] = None,
        notes: Optional[str] = None,
        affects_stock: bool = True,
        is_historical: bool = False,
        created_by=None,
    ) -> Sale:
        """
        Record a sale transaction.
        
        1. Validate products and quantities
        2. Check sufficient stock (if affects_stock)
        3. Consume stock using FEFO
        4. Create sale + sale_items
        5. Record stock movements
        
        All within a single DB transaction.
        """
        if not items:
            raise ValueError("Sale must have at least one item")

        sale_number = await SalesService.generate_sale_number(db)
        if sale_date is None:
            sale_date = datetime.now(timezone.utc)

        total_amount = Decimal("0")
        sale_items = []

        # Create sale header first
        sale = Sale(
            sale_number=sale_number,
            sale_date=sale_date,
            total_amount=Decimal("0"),
            total_items=len(items),
            reference_number=reference_number,
            status="COMPLETED",
            notes=notes,
            is_historical_import=is_historical,
            affects_stock=affects_stock,
            created_by=created_by,
        )
        db.add(sale)
        await db.flush()

        for item_data in items:
            product_id = item_data.product_id
            quantity = Decimal(str(item_data.quantity))
            unit_price = Decimal(str(item_data.unit_price))

            # Validate product
            product = await db.get(Product, product_id)
            if not product:
                raise ValueError(f"Product with ID {product_id} not found")
            if not product.is_active:
                raise ValueError(f"Product '{product.name}' is inactive")

            if quantity <= 0:
                raise ValueError(f"Quantity must be positive for product '{product.name}'")

            line_total = quantity * unit_price
            total_amount += line_total

            # Create sale item
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product_id,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
            db.add(sale_item)
            sale_items.append(sale_item)

            # Consume stock using FEFO (if this sale affects stock)
            if affects_stock:
                await InventoryService.consume_stock_fefo(
                    db=db,
                    product_id=product_id,
                    quantity=quantity,
                    movement_type="SALE",
                    reference_type="SALE",
                    reference_id=sale.id,
                    notes=f"Sale #{sale_number}: {quantity} × {product.name}",
                )

        # Update sale total
        sale.total_amount = total_amount

        return sale

    @staticmethod
    async def cancel_sale(db: AsyncSession, sale_id: int) -> Sale:
        """
        Cancel a sale by creating compensating stock movements.
        Does not delete records — creates reversal entries.
        """
        sale = await db.get(Sale, sale_id)
        if not sale:
            raise ValueError(f"Sale with ID {sale_id} not found")
        if sale.status == "CANCELLED":
            raise ValueError(f"Sale {sale.sale_number} is already cancelled")

        # Reverse stock movements if the sale affected stock
        if sale.affects_stock:
            await InventoryService.reverse_sale_movements(db, sale_id)

        sale.status = "CANCELLED"
        return sale

    @staticmethod
    async def get_sales(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Get paginated sales list."""
        query = select(Sale).order_by(Sale.sale_date.desc())

        if status:
            query = query.where(Sale.status == status)
        if start_date:
            query = query.where(Sale.sale_date >= start_date)
        if end_date:
            query = query.where(Sale.sale_date <= end_date)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        sales = result.scalars().all()

        return sales, total
