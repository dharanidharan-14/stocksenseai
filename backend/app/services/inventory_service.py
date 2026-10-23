"""
StockSense AI - Inventory Service

Core inventory operations: stock receipts, adjustments, FEFO consumption,
and batch management. All operations are transactionally safe.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryBatch, StockMovement
from app.models.product import Product


class InventoryService:
    """Handles all inventory mutations with audit trail."""

    @staticmethod
    async def get_usable_stock(
        db: AsyncSession, product_id: int, today: Optional[date] = None
    ) -> Decimal:
        """
        Get total usable (non-expired) stock for a product.
        Excludes batches that have expired before today.
        """
        if today is None:
            today = date.today()

        result = await db.execute(
            select(func.coalesce(func.sum(InventoryBatch.remaining_quantity), Decimal("0")))
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.remaining_quantity > 0,
                or_(
                    InventoryBatch.expiry_date.is_(None),
                    InventoryBatch.expiry_date > today,
                ),
            )
        )
        return result.scalar() or Decimal("0")

    @staticmethod
    async def get_total_stock(db: AsyncSession, product_id: int) -> Decimal:
        """Get total stock for a product (including expired)."""
        result = await db.execute(
            select(func.coalesce(func.sum(InventoryBatch.remaining_quantity), Decimal("0")))
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.remaining_quantity > 0,
            )
        )
        return result.scalar() or Decimal("0")

    @staticmethod
    async def get_expired_stock(
        db: AsyncSession, product_id: int, today: Optional[date] = None
    ) -> Decimal:
        """Get total expired stock for a product."""
        if today is None:
            today = date.today()

        result = await db.execute(
            select(func.coalesce(func.sum(InventoryBatch.remaining_quantity), Decimal("0")))
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.remaining_quantity > 0,
                InventoryBatch.expiry_date.isnot(None),
                InventoryBatch.expiry_date <= today,
            )
        )
        return result.scalar() or Decimal("0")

    @staticmethod
    async def create_stock_receipt(
        db: AsyncSession,
        product_id: int,
        quantity: Decimal,
        unit_cost: Decimal,
        batch_number: Optional[str] = None,
        manufacture_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
        receipt_reference: Optional[str] = None,
        source_type: str = "OPENING",
        source_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Tuple[InventoryBatch, StockMovement]:
        """
        Create a new inventory batch and stock movement.
        Used for opening stock, direct receipts, and purchase order receipts.
        """
        # Validate product exists
        product = await db.get(Product, product_id)
        if not product:
            raise ValueError(f"Product with ID {product_id} not found")

        if quantity <= 0:
            raise ValueError("Receipt quantity must be positive")

        # Create the batch
        batch = InventoryBatch(
            product_id=product_id,
            batch_number=batch_number,
            received_quantity=quantity,
            remaining_quantity=quantity,
            unit_cost=unit_cost,
            manufacture_date=manufacture_date,
            expiry_date=expiry_date,
            receipt_reference=receipt_reference,
            source_type=source_type,
            source_id=source_id,
        )
        db.add(batch)
        await db.flush()

        # Create stock movement
        movement = StockMovement(
            product_id=product_id,
            batch_id=batch.id,
            movement_type="RECEIPT" if source_type == "PURCHASE" else source_type,
            quantity=quantity,
            reference_type=source_type,
            reference_id=source_id,
            notes=notes or f"Stock receipt: {quantity} units",
        )
        db.add(movement)

        return batch, movement

    @staticmethod
    async def create_adjustment(
        db: AsyncSession,
        product_id: int,
        adjustment_type: str,
        quantity: Decimal,
        batch_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> StockMovement:
        """
        Create a stock adjustment (positive=add, negative=remove).
        For positive adjustments without a batch, creates a new batch.
        For negative adjustments, removes from specified batch or FEFO.
        """
        product = await db.get(Product, product_id)
        if not product:
            raise ValueError(f"Product with ID {product_id} not found")

        if quantity > 0:
            # Adding stock — create a new adjustment batch
            batch = InventoryBatch(
                product_id=product_id,
                received_quantity=quantity,
                remaining_quantity=quantity,
                unit_cost=product.purchase_cost,
                source_type="ADJUSTMENT",
            )
            db.add(batch)
            await db.flush()

            movement = StockMovement(
                product_id=product_id,
                batch_id=batch.id,
                movement_type=adjustment_type,
                quantity=quantity,
                reference_type="ADJUSTMENT",
                notes=notes or f"Stock adjustment: +{quantity}",
            )
            db.add(movement)
            return movement

        elif quantity < 0:
            # Removing stock
            abs_qty = abs(quantity)

            if batch_id:
                # Remove from specific batch
                batch = await db.get(InventoryBatch, batch_id)
                if not batch or batch.product_id != product_id:
                    raise ValueError("Invalid batch for this product")
                if batch.remaining_quantity < abs_qty:
                    raise ValueError(
                        f"Insufficient stock in batch {batch_id}: "
                        f"has {batch.remaining_quantity}, need {abs_qty}"
                    )
                batch.remaining_quantity -= abs_qty

                movement = StockMovement(
                    product_id=product_id,
                    batch_id=batch_id,
                    movement_type=adjustment_type,
                    quantity=quantity,  # negative
                    reference_type="ADJUSTMENT",
                    notes=notes or f"Stock adjustment: {quantity}",
                )
                db.add(movement)
                return movement
            else:
                # Use FEFO to consume
                movements = await InventoryService.consume_stock_fefo(
                    db, product_id, abs_qty, adjustment_type, "ADJUSTMENT", notes=notes
                )
                return movements[0] if movements else None
        else:
            raise ValueError("Adjustment quantity cannot be zero")

    @staticmethod
    async def consume_stock_fefo(
        db: AsyncSession,
        product_id: int,
        quantity: Decimal,
        movement_type: str = "SALE",
        reference_type: str = "SALE",
        reference_id: Optional[int] = None,
        notes: Optional[str] = None,
        today: Optional[date] = None,
    ) -> List[StockMovement]:
        """
        Consume stock using FEFO (First Expiry, First Out).
        
        Order:
        1. Batches with earliest expiry date first (non-expired only)
        2. Batches with no expiry date last
        
        Returns list of stock movements created.
        Raises ValueError if insufficient usable stock.
        """
        if today is None:
            today = date.today()

        # Check usable stock first
        usable = await InventoryService.get_usable_stock(db, product_id, today)
        if usable < quantity:
            raise ValueError(
                f"Insufficient usable stock for product {product_id}: "
                f"available {usable}, requested {quantity}"
            )

        # Fetch eligible batches in FEFO order with row-level locking
        result = await db.execute(
            select(InventoryBatch)
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.remaining_quantity > 0,
                or_(
                    InventoryBatch.expiry_date.is_(None),
                    InventoryBatch.expiry_date > today,
                ),
            )
            .order_by(
                # Batches WITH expiry first (NULLS LAST), then by earliest expiry
                case(
                    (InventoryBatch.expiry_date.is_(None), 1),
                    else_=0,
                ),
                InventoryBatch.expiry_date.asc(),
                InventoryBatch.created_at.asc(),
            )
            .with_for_update()
        )
        batches = result.scalars().all()

        remaining_to_consume = quantity
        movements = []

        for batch in batches:
            if remaining_to_consume <= 0:
                break

            consume_from_batch = min(batch.remaining_quantity, remaining_to_consume)
            batch.remaining_quantity -= consume_from_batch
            remaining_to_consume -= consume_from_batch

            movement = StockMovement(
                product_id=product_id,
                batch_id=batch.id,
                movement_type=movement_type,
                quantity=-consume_from_batch,  # Negative for outflow
                reference_type=reference_type,
                reference_id=reference_id,
                notes=notes or f"Stock consumed: {consume_from_batch} from batch {batch.id}",
            )
            db.add(movement)
            movements.append(movement)

        if remaining_to_consume > 0:
            raise ValueError(
                f"Could not fully consume {quantity} for product {product_id}. "
                f"Remaining: {remaining_to_consume}"
            )

        await db.flush()
        return movements

    @staticmethod
    async def reverse_sale_movements(
        db: AsyncSession,
        sale_id: int,
    ) -> List[StockMovement]:
        """
        Create compensating stock movements to reverse a sale.
        Adds stock back to the original batches.
        """
        # Find all movements related to this sale
        result = await db.execute(
            select(StockMovement)
            .where(
                StockMovement.reference_type == "SALE",
                StockMovement.reference_id == sale_id,
                StockMovement.movement_type == "SALE",
            )
        )
        sale_movements = result.scalars().all()

        if not sale_movements:
            raise ValueError(f"No stock movements found for sale {sale_id}")

        reversal_movements = []
        for original in sale_movements:
            # Restore stock to the batch
            if original.batch_id:
                batch = await db.get(InventoryBatch, original.batch_id)
                if batch:
                    batch.remaining_quantity += abs(original.quantity)

            # Create reversal movement
            reversal = StockMovement(
                product_id=original.product_id,
                batch_id=original.batch_id,
                movement_type="REVERSAL",
                quantity=abs(original.quantity),  # Positive for stock return
                reference_type="SALE_REVERSAL",
                reference_id=sale_id,
                notes=f"Reversal of sale #{sale_id}, restoring {abs(original.quantity)} units",
            )
            db.add(reversal)
            reversal_movements.append(reversal)

        return reversal_movements

    @staticmethod
    async def get_inventory_summary(db: AsyncSession) -> dict:
        """Get a summary of current inventory state."""
        today = date.today()

        # Get all active products with batch aggregates
        result = await db.execute(
            select(Product)
            .where(Product.is_active == True)
            .order_by(Product.name)
        )
        products = result.scalars().all()

        items = []
        total_value = Decimal("0")
        low_stock_count = 0
        out_of_stock_count = 0

        for product in products:
            usable = await InventoryService.get_usable_stock(db, product.id, today)
            expired = await InventoryService.get_expired_stock(db, product.id, today)
            total = usable + expired

            # Count batches
            batch_result = await db.execute(
                select(func.count(InventoryBatch.id))
                .where(
                    InventoryBatch.product_id == product.id,
                    InventoryBatch.remaining_quantity > 0,
                )
            )
            batch_count = batch_result.scalar() or 0

            value = usable * product.purchase_cost
            total_value += value
            is_low = usable <= product.reorder_threshold

            if usable <= 0:
                out_of_stock_count += 1
            elif is_low:
                low_stock_count += 1

            items.append({
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "unit": product.unit,
                "total_stock": total,
                "usable_stock": usable,
                "expired_stock": expired,
                "total_value": value,
                "reorder_threshold": product.reorder_threshold,
                "is_low_stock": is_low,
                "batch_count": batch_count,
            })

        return {
            "items": items,
            "total_products": len(products),
            "total_value": total_value,
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
        }
