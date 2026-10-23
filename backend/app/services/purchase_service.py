"""
StockSense AI - Purchase Service

Handles purchase order lifecycle: draft → ordered → partially received → received.
Receipt processing creates inventory batches and stock movements transactionally.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase import (
    PurchaseOrder, PurchaseOrderItem,
    PurchaseReceipt, PurchaseReceiptItem,
)
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_service import InventoryService


class PurchaseService:
    """Handles purchase order lifecycle."""

    @staticmethod
    async def generate_po_number(db: AsyncSession) -> str:
        """Generate a unique PO number."""
        result = await db.execute(select(func.count(PurchaseOrder.id)))
        count = result.scalar() or 0
        now = datetime.now(timezone.utc)
        return f"PO-{now.strftime('%Y%m%d')}-{count + 1:04d}"

    @staticmethod
    async def generate_receipt_number(db: AsyncSession) -> str:
        """Generate a unique receipt number."""
        result = await db.execute(select(func.count(PurchaseReceipt.id)))
        count = result.scalar() or 0
        now = datetime.now(timezone.utc)
        return f"RCV-{now.strftime('%Y%m%d')}-{count + 1:04d}"

    @staticmethod
    async def create_purchase_order(
        db: AsyncSession,
        supplier_id: int,
        items: list,
        order_date: Optional[date] = None,
        expected_delivery_date: Optional[date] = None,
        notes: Optional[str] = None,
        created_by=None,
    ) -> PurchaseOrder:
        """Create a draft purchase order."""
        # Validate supplier
        supplier = await db.get(Supplier, supplier_id)
        if not supplier:
            raise ValueError(f"Supplier with ID {supplier_id} not found")

        po_number = await PurchaseService.generate_po_number(db)
        if order_date is None:
            order_date = date.today()

        po = PurchaseOrder(
            po_number=po_number,
            supplier_id=supplier_id,
            order_date=order_date,
            expected_delivery_date=expected_delivery_date,
            status="DRAFT",
            notes=notes,
            created_by=created_by,
        )
        db.add(po)
        await db.flush()

        total = Decimal("0")
        for item_data in items:
            product = await db.get(Product, item_data.product_id)
            if not product:
                raise ValueError(f"Product with ID {item_data.product_id} not found")

            line_total = Decimal(str(item_data.ordered_quantity)) * Decimal(str(item_data.unit_cost))
            total += line_total

            po_item = PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=item_data.product_id,
                ordered_quantity=Decimal(str(item_data.ordered_quantity)),
                unit_cost=Decimal(str(item_data.unit_cost)),
                line_total=line_total,
            )
            db.add(po_item)

        po.total_amount = total
        return po

    @staticmethod
    async def confirm_order(db: AsyncSession, po_id: int) -> PurchaseOrder:
        """Confirm a draft purchase order (mark as ORDERED)."""
        po = await db.get(PurchaseOrder, po_id)
        if not po:
            raise ValueError(f"Purchase order {po_id} not found")
        if po.status != "DRAFT":
            raise ValueError(f"Can only confirm DRAFT orders, current status: {po.status}")

        po.status = "ORDERED"
        return po

    @staticmethod
    async def cancel_order(db: AsyncSession, po_id: int) -> PurchaseOrder:
        """Cancel a purchase order. Only DRAFT or ORDERED can be cancelled."""
        po = await db.get(PurchaseOrder, po_id)
        if not po:
            raise ValueError(f"Purchase order {po_id} not found")
        if po.status not in ("DRAFT", "ORDERED"):
            raise ValueError(
                f"Cannot cancel order with status '{po.status}'. "
                f"Only DRAFT or ORDERED orders can be cancelled."
            )

        po.status = "CANCELLED"
        return po

    @staticmethod
    async def receive_order(
        db: AsyncSession,
        po_id: int,
        receipt_items: list,
        receipt_date: Optional[date] = None,
        notes: Optional[str] = None,
        created_by=None,
    ) -> PurchaseReceipt:
        """
        Process a receipt against a purchase order.
        
        1. Validate PO status (must be ORDERED or PARTIALLY_RECEIVED)
        2. Validate receipt quantities don't exceed remaining
        3. Create inventory batches
        4. Create stock movements
        5. Update PO item received quantities
        6. Update PO status
        
        All within a transaction.
        """
        po = await db.get(PurchaseOrder, po_id)
        if not po:
            raise ValueError(f"Purchase order {po_id} not found")
        if po.status not in ("ORDERED", "PARTIALLY_RECEIVED"):
            raise ValueError(
                f"Cannot receive order with status '{po.status}'. "
                f"Order must be ORDERED or PARTIALLY_RECEIVED."
            )

        if receipt_date is None:
            receipt_date = date.today()

        receipt_number = await PurchaseService.generate_receipt_number(db)

        # Create receipt header
        receipt = PurchaseReceipt(
            purchase_order_id=po_id,
            receipt_number=receipt_number,
            receipt_date=receipt_date,
            notes=notes,
            created_by=created_by,
        )
        db.add(receipt)
        await db.flush()

        # Load PO items
        po_items_result = await db.execute(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.purchase_order_id == po_id
            )
        )
        po_items_map = {
            item.id: item for item in po_items_result.scalars().all()
        }

        receipt_item_records = []
        for ri in receipt_items:
            po_item = po_items_map.get(ri.purchase_order_item_id)
            if not po_item:
                raise ValueError(
                    f"PO item {ri.purchase_order_item_id} not found in PO {po.po_number}"
                )

            remaining = po_item.ordered_quantity - po_item.received_quantity
            qty = Decimal(str(ri.quantity_received))

            if qty > remaining:
                raise ValueError(
                    f"Received quantity ({qty}) exceeds remaining ({remaining}) "
                    f"for PO item {po_item.id}"
                )

            unit_cost = Decimal(str(ri.unit_cost)) if ri.unit_cost else po_item.unit_cost

            # Create inventory batch
            batch, movement = await InventoryService.create_stock_receipt(
                db=db,
                product_id=po_item.product_id,
                quantity=qty,
                unit_cost=unit_cost,
                batch_number=ri.batch_number,
                manufacture_date=ri.manufacture_date,
                expiry_date=ri.expiry_date,
                receipt_reference=receipt_number,
                source_type="PURCHASE",
                source_id=receipt.id,
                notes=f"Receipt from PO #{po.po_number}",
            )

            # Create receipt item
            receipt_item = PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                purchase_order_item_id=po_item.id,
                product_id=po_item.product_id,
                quantity_received=qty,
                unit_cost=unit_cost,
                batch_number=ri.batch_number,
                manufacture_date=ri.manufacture_date,
                expiry_date=ri.expiry_date,
                batch_id=batch.id,
            )
            db.add(receipt_item)
            receipt_item_records.append(receipt_item)

            # Update PO item received quantity
            po_item.received_quantity += qty

        # Determine new PO status
        all_received = all(
            item.received_quantity >= item.ordered_quantity
            for item in po_items_map.values()
        )
        any_received = any(
            item.received_quantity > 0
            for item in po_items_map.values()
        )

        if all_received:
            po.status = "RECEIVED"
        elif any_received:
            po.status = "PARTIALLY_RECEIVED"

        await db.flush()
        return receipt

    @staticmethod
    async def get_incoming_stock(db: AsyncSession, product_id: int) -> Decimal:
        """
        Get total incoming (ordered but not yet received) stock for a product.
        Only from ORDERED or PARTIALLY_RECEIVED purchase orders.
        """
        result = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        PurchaseOrderItem.ordered_quantity - PurchaseOrderItem.received_quantity
                    ),
                    Decimal("0"),
                )
            )
            .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .where(
                PurchaseOrderItem.product_id == product_id,
                PurchaseOrder.status.in_(["ORDERED", "PARTIALLY_RECEIVED"]),
            )
        )
        return result.scalar() or Decimal("0")
