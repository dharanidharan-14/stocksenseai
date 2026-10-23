"""
StockSense AI - Voice Assistant Tests
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import date, timedelta
from app.services.assistant_service import AssistantService
from app.models.product import Product
from app.models.inventory import InventoryBatch
from app.services.inventory_service import InventoryService


@pytest_asyncio.fixture
async def seed_assistant_data(db_session):
    """Seed sample products and batches for testing assistant queries in test DB."""
    rice = Product(
        name="India Gate Basmati Rice 5kg",
        sku="GRN-RICE-001",
        unit="packet",
        purchase_cost=Decimal("380"),
        selling_price=Decimal("440"),
        reorder_threshold=Decimal("15"),
        safety_stock=Decimal("10"),
        is_active=True,
    )
    milk = Product(
        name="Amul Taaza Toned Milk 500ml",
        sku="DAI-MILK-001",
        unit="packet",
        purchase_cost=Decimal("24"),
        selling_price=Decimal("28"),
        reorder_threshold=Decimal("10"),
        safety_stock=Decimal("5"),
        is_active=True,
    )
    biscuit = Product(
        name="Parle-G Glucose Biscuits 1kg",
        sku="SNK-BISC-001",
        unit="packet",
        purchase_cost=Decimal("80"),
        selling_price=Decimal("100"),
        reorder_threshold=Decimal("20"),
        safety_stock=Decimal("10"),
        is_active=True,
    )
    db_session.add_all([rice, milk, biscuit])
    await db_session.flush()

    # Add active batch for rice and milk
    today = date.today()
    batch_rice = InventoryBatch(
        product_id=rice.id,
        batch_number="BAT-RICE-01",
        received_quantity=Decimal("25"),
        remaining_quantity=Decimal("25"),
        unit_cost=Decimal("380"),
        expiry_date=today + timedelta(days=180),
        source_type="OPENING",
    )
    batch_milk = InventoryBatch(
        product_id=milk.id,
        batch_number="BAT-MILK-01",
        received_quantity=Decimal("20"),
        remaining_quantity=Decimal("20"),
        unit_cost=Decimal("24"),
        expiry_date=today + timedelta(days=2),
        source_type="OPENING",
    )
    db_session.add_all([batch_rice, batch_milk])
    await db_session.commit()
    return {"rice": rice, "milk": milk, "biscuit": biscuit}


@pytest.mark.asyncio
async def test_assistant_check_rice_stock(db_session, seed_assistant_data):
    resp = await AssistantService.process_command(db_session, "How much rice stock is left?")
    assert resp.intent == "CHECK_STOCK"
    assert "25" in resp.speech_text
    assert resp.data is not None
    assert resp.data["usable_stock"] == Decimal("25")
    assert resp.requires_confirmation is False


@pytest.mark.asyncio
async def test_assistant_check_low_stock(db_session, seed_assistant_data):
    resp = await AssistantService.process_command(db_session, "Which products are running low?")
    assert resp.intent == "CHECK_LOW_STOCK"
    assert resp.requires_confirmation is False


@pytest.mark.asyncio
async def test_assistant_check_out_of_stock(db_session, seed_assistant_data):
    resp = await AssistantService.process_command(db_session, "Show all products currently out of stock.")
    assert resp.intent == "CHECK_OUT_OF_STOCK"
    assert resp.requires_confirmation is False


@pytest.mark.asyncio
async def test_assistant_expiry_queries(db_session, seed_assistant_data):
    resp_7days = await AssistantService.process_command(db_session, "Show products expiring in the next seven days.")
    assert resp_7days.intent == "CHECK_EXPIRY"

    resp_expired = await AssistantService.process_command(db_session, "Show expired products.")
    assert resp_expired.intent == "CHECK_EXPIRY"


@pytest.mark.asyncio
async def test_assistant_record_sale_gate(db_session, seed_assistant_data):
    # 1. Sale command must ask for confirmation first
    resp = await AssistantService.process_command(db_session, "Record a sale of 2 milk packets.")
    assert resp.intent == "RECORD_SALE"
    assert resp.requires_confirmation is True
    assert resp.action_payload is not None
    assert resp.action_payload["action"] == "RECORD_SALE"
    assert resp.action_payload["quantity"] == 2.0

    # 2. Confirm the sale
    confirmed_resp = await AssistantService.process_command(
        db_session,
        command_text="",
        confirmed=True,
        action_payload=resp.action_payload
    )
    assert confirmed_resp.intent == "RECORD_SALE"
    assert "recorded successfully" in confirmed_resp.speech_text.lower()
    assert confirmed_resp.data is not None
    assert "sale_number" in confirmed_resp.data

    # Verify stock deducted by 2
    milk = seed_assistant_data["milk"]
    stock = await InventoryService.get_usable_stock(db_session, milk.id)
    assert stock == Decimal("18")


@pytest.mark.asyncio
async def test_assistant_receive_stock_gate(db_session, seed_assistant_data):
    resp = await AssistantService.process_command(db_session, "We received 10 biscuit packets.")
    assert resp.intent == "RECEIVE_STOCK"
    assert resp.requires_confirmation is True
    assert resp.action_payload is not None
    assert resp.action_payload["action"] == "RECEIVE_STOCK"

    # Confirm stock receipt
    confirmed_resp = await AssistantService.process_command(
        db_session,
        command_text="",
        confirmed=True,
        action_payload=resp.action_payload
    )
    assert confirmed_resp.intent == "RECEIVE_STOCK"
    assert "stock received" in confirmed_resp.speech_text.lower()

    biscuit = seed_assistant_data["biscuit"]
    stock = await InventoryService.get_usable_stock(db_session, biscuit.id)
    assert stock == Decimal("10")


@pytest.mark.asyncio
async def test_assistant_sales_info(db_session, seed_assistant_data):
    resp = await AssistantService.process_command(db_session, "How much did I sell today?")
    assert resp.intent == "SALES_INFO"
    assert "today" in resp.speech_text.lower() or "sales" in resp.speech_text.lower()


@pytest.mark.asyncio
async def test_assistant_ai_recommendations(db_session, seed_assistant_data):
    resp = await AssistantService.process_command(db_session, "What should I reorder today?")
    assert resp.intent == "AI_RECOMMENDATION"

    budget_resp = await AssistantService.process_command(db_session, "Recommend purchases within my 2,000 rupee budget.")
    assert budget_resp.intent == "AI_RECOMMENDATION"
