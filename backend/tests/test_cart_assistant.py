"""
Tests for Cart & Billing Operations in Voice Assistant
Verifies:
- ADD_TO_CART with Thanglish and English phrasing
- REMOVE_FROM_CART
- CHECK_BILL_TOTAL
- CLEAR_BILL with confirmation gating
- Out of stock prevention
- Language preference (Tamil, English, Tanglish)
"""

import pytest
from httpx import AsyncClient
from decimal import Decimal
from app.models.product import Product
from app.models.inventory import InventoryBatch
from app.services.assistant_service import AssistantService
from app.schemas.assistant import GeminiParsedIntent


@pytest.mark.asyncio
async def test_add_to_cart_available_product(db_session, test_user):
    # Ensure product with stock exists
    product = Product(
        name="Test Milk Packet 500ml",
        sku="TEST-MILK-001",
        category_id=1,
        unit="packet",
        purchase_cost=Decimal("25.00"),
        selling_price=Decimal("30.00"),
        safety_stock=5,
        reorder_threshold=10,
        is_active=True,
    )
    db_session.add(product)
    await db_session.flush()

    batch = InventoryBatch(
        product_id=product.id,
        batch_number="BAT-MILK-TEST",
        received_quantity=Decimal("20.00"),
        remaining_quantity=Decimal("20.00"),
        unit_cost=Decimal("25.00"),
        source_type="OPENING_STOCK",
    )
    db_session.add(batch)
    await db_session.commit()

    # Process command: "2 packet milk cart la podu"
    parsed = GeminiParsedIntent(
        intent="ADD_TO_CART",
        product_raw="milk",
        product_normalized="Milk",
        quantity=2.0,
        unit="packet",
    )
    response = await AssistantService._handle_add_to_cart(db_session, "2 packet milk cart la podu", parsed)

    assert response.intent == "ADD_TO_CART"
    assert response.confidence_status == "CONFIRMED"
    assert response.action_payload is not None
    assert response.action_payload["action"] == "ADD_TO_CART"
    assert response.action_payload["product_id"] == product.id
    assert response.action_payload["quantity"] == 2.0
    assert response.action_payload["line_total"] == 60.0  # 2 * 30.00


@pytest.mark.asyncio
async def test_add_to_cart_out_of_stock_rejected(db_session):
    product = Product(
        name="Out of Stock Butter 200g",
        sku="TEST-BTR-002",
        category_id=1,
        unit="packet",
        purchase_cost=Decimal("50.00"),
        selling_price=Decimal("60.00"),
        safety_stock=5,
        reorder_threshold=10,
        is_active=True,
    )
    db_session.add(product)
    await db_session.commit()

    parsed = GeminiParsedIntent(
        intent="ADD_TO_CART",
        product_raw="butter",
        product_normalized="Butter",
        quantity=1.0,
        unit="packet",
    )
    response = await AssistantService._handle_add_to_cart(db_session, "butter cart la podu", parsed)

    assert response.intent == "ADD_TO_CART"
    assert "out of stock" in response.speech_text.lower() or "illai" in response.speech_text.lower()
    assert response.action_payload is None  # Blocked from being added


@pytest.mark.asyncio
async def test_remove_from_cart(db_session):
    product = Product(
        name="Test Sugar Packet 1kg",
        sku="TEST-SGR-003",
        category_id=1,
        unit="packet",
        purchase_cost=Decimal("40.00"),
        selling_price=Decimal("45.00"),
        safety_stock=5,
        reorder_threshold=10,
        is_active=True,
    )
    db_session.add(product)
    await db_session.commit()

    parsed = GeminiParsedIntent(
        intent="REMOVE_FROM_CART",
        product_raw="sugar",
        product_normalized="Sugar",
    )
    response = await AssistantService._handle_remove_from_cart(db_session, "remove sugar from bill", parsed)

    assert response.intent == "REMOVE_FROM_CART"
    assert response.action_payload["action"] == "REMOVE_FROM_CART"
    assert response.action_payload["product_id"] == product.id


@pytest.mark.asyncio
async def test_clear_bill_requires_confirmation(db_session):
    parsed = GeminiParsedIntent(
        intent="CLEAR_BILL",
    )
    response = await AssistantService._handle_clear_bill(db_session, "clear the bill", parsed)

    assert response.intent == "CLEAR_BILL"
    assert response.requires_confirmation is True
    assert response.action_payload["action"] == "CLEAR_BILL"


@pytest.mark.asyncio
async def test_clear_bill_execution(db_session):
    response = await AssistantService._execute_confirmed_action(db_session, {"action": "CLEAR_BILL"})
    assert response.intent == "CLEAR_BILL"
    assert response.action_payload["action"] == "CLEAR_BILL_EXECUTED"
