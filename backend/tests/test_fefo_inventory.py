"""
StockSense AI - FEFO Inventory Allocation Unit & Integration Tests
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.models.product import Category, Product
from app.models.inventory import InventoryBatch
from app.services.inventory_service import InventoryService


@pytest.mark.asyncio
async def test_fefo_earliest_expiry_consumed_first(db_session):
    today = date.today()

    # Create category & product
    cat = Category(name="Staples")
    db_session.add(cat)
    await db_session.flush()

    prod = Product(
        name="Test Milk",
        sku="TEST-MILK-01",
        category_id=cat.id,
        unit="packet",
        purchase_cost=Decimal("25.00"),
        selling_price=Decimal("30.00"),
    )
    db_session.add(prod)
    await db_session.flush()

    # Batch 1: Expiring in 2 days (10 units)
    b1, _ = await InventoryService.create_stock_receipt(
        db_session,
        product_id=prod.id,
        quantity=Decimal("10"),
        unit_cost=Decimal("25.00"),
        batch_number="BATCH-EARLY",
        expiry_date=today + timedelta(days=2),
    )

    # Batch 2: Expiring in 10 days (20 units)
    b2, _ = await InventoryService.create_stock_receipt(
        db_session,
        product_id=prod.id,
        quantity=Decimal("20"),
        unit_cost=Decimal("25.00"),
        batch_number="BATCH-LATE",
        expiry_date=today + timedelta(days=10),
    )

    # Batch 3: Non-expiring (15 units)
    b3, _ = await InventoryService.create_stock_receipt(
        db_session,
        product_id=prod.id,
        quantity=Decimal("15"),
        unit_cost=Decimal("25.00"),
        batch_number="BATCH-NO-EXP",
        expiry_date=None,
    )

    # Total usable stock: 10 + 20 + 15 = 45
    usable = await InventoryService.get_usable_stock(db_session, prod.id, today)
    assert usable == Decimal("45")

    # Consume 15 units via FEFO:
    # Should consume all 10 from Batch 1, and 5 from Batch 2!
    movements = await InventoryService.consume_stock_fefo(
        db_session,
        product_id=prod.id,
        quantity=Decimal("15"),
        movement_type="SALE",
        today=today,
    )

    assert len(movements) == 2

    # Verify batch remaining quantities
    await db_session.refresh(b1)
    await db_session.refresh(b2)
    await db_session.refresh(b3)

    assert b1.remaining_quantity == Decimal("0")   # fully consumed
    assert b2.remaining_quantity == Decimal("15")  # 20 - 5 = 15
    assert b3.remaining_quantity == Decimal("15")  # untouched


@pytest.mark.asyncio
async def test_fefo_ignores_already_expired_batches(db_session):
    today = date.today()

    cat = Category(name="Dairy")
    db_session.add(cat)
    await db_session.flush()

    prod = Product(
        name="Test Yogurt",
        sku="TEST-YOG-01",
        category_id=cat.id,
        unit="cup",
        purchase_cost=Decimal("15.00"),
        selling_price=Decimal("20.00"),
    )
    db_session.add(prod)
    await db_session.flush()

    # Expired batch: Expired yesterday (5 units)
    b_exp, _ = await InventoryService.create_stock_receipt(
        db_session,
        product_id=prod.id,
        quantity=Decimal("5"),
        unit_cost=Decimal("15.00"),
        batch_number="BATCH-EXPIRED",
        expiry_date=today - timedelta(days=1),
    )

    # Fresh batch: Expiring next week (10 units)
    b_fresh, _ = await InventoryService.create_stock_receipt(
        db_session,
        product_id=prod.id,
        quantity=Decimal("10"),
        unit_cost=Decimal("15.00"),
        batch_number="BATCH-FRESH",
        expiry_date=today + timedelta(days=7),
    )

    usable = await InventoryService.get_usable_stock(db_session, prod.id, today)
    expired = await InventoryService.get_expired_stock(db_session, prod.id, today)

    assert usable == Decimal("10")
    assert expired == Decimal("5")

    # Requesting 12 units should fail because expired stock cannot be sold!
    with pytest.raises(ValueError, match="Insufficient usable stock"):
        await InventoryService.consume_stock_fefo(
            db_session,
            product_id=prod.id,
            quantity=Decimal("12"),
            movement_type="SALE",
            today=today,
        )
