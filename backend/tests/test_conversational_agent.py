"""
StockSense AI - Conversational AI Agent Tests
Tests for multi-turn conversations, Tanglish / Tamil queries,
cancellations, corrections, and confirmation gates.
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import date, timedelta
from app.services.assistant_service import AssistantService
from app.models.product import Product
from app.models.inventory import InventoryBatch
from app.services.inventory_service import InventoryService
from app.services.session_store import SessionStore


@pytest_asyncio.fixture
async def seed_conversational_data(db_session):
    """Seed sample products and batches for multi-turn and Tanglish testing."""
    tomato = Product(
        name="Fresh Country Tomato 1kg",
        sku="VEG-TOM-001",
        unit="kg",
        purchase_cost=Decimal("30"),
        selling_price=Decimal("45"),
        reorder_threshold=Decimal("10"),
        safety_stock=Decimal("5"),
        is_active=True,
    )
    milk = Product(
        name="Aavin Green Milk 500ml",
        sku="DAI-MILK-002",
        unit="packet",
        purchase_cost=Decimal("22"),
        selling_price=Decimal("25"),
        reorder_threshold=Decimal("15"),
        safety_stock=Decimal("8"),
        is_active=True,
    )
    rice = Product(
        name="Ponni Boiled Rice 25kg",
        sku="GRN-RICE-002",
        unit="bag",
        purchase_cost=Decimal("1200"),
        selling_price=Decimal("1450"),
        reorder_threshold=Decimal("5"),
        safety_stock=Decimal("2"),
        is_active=True,
    )
    db_session.add_all([tomato, milk, rice])
    await db_session.flush()

    today = date.today()
    batch_tomato = InventoryBatch(
        product_id=tomato.id,
        batch_number="BAT-TOM-01",
        received_quantity=Decimal("35"),
        remaining_quantity=Decimal("35"),
        unit_cost=Decimal("30"),
        expiry_date=today + timedelta(days=5),
        source_type="OPENING",
    )
    batch_milk = InventoryBatch(
        product_id=milk.id,
        batch_number="BAT-MILK-02",
        received_quantity=Decimal("40"),
        remaining_quantity=Decimal("40"),
        unit_cost=Decimal("22"),
        expiry_date=today + timedelta(days=2),
        source_type="OPENING",
    )
    db_session.add_all([batch_tomato, batch_milk])
    await db_session.commit()
    return {"tomato": tomato, "milk": milk, "rice": rice}


@pytest.mark.asyncio
async def test_tanglish_stock_query(db_session, seed_conversational_data):
    """Test Tanglish query: 'Thakkali stock la evlo irukku?'"""
    session_id = "test_tanglish_query"
    resp = await AssistantService.process_command(
        db_session,
        "Thakkali stock la evlo irukku?",
        session_id=session_id
    )
    assert resp.intent in ("CHECK_STOCK", "STOCK_INFO")
    assert resp.requires_confirmation is False
    assert resp.data is not None
    assert resp.data["usable_stock"] == Decimal("35")


@pytest.mark.asyncio
async def test_conversational_cancellation_flow(db_session, seed_conversational_data):
    """
    Test proposal -> cancellation turn:
    1. 'Record sale of 2 milk packets' -> proposals created, awaiting confirmation.
    2. 'Cancel pannidu' -> proposal aborted, 0 stock deducted.
    """
    session_id = "test_cancel_flow"
    SessionStore.clear_session(session_id)

    # Turn 1: Propose sale
    resp1 = await AssistantService.process_command(
        db_session,
        "Record a sale of 2 milk packets",
        session_id=session_id
    )
    assert resp1.intent == "RECORD_SALE"
    assert resp1.requires_confirmation is True
    assert SessionStore.get_pending_proposal(session_id) is not None

    # Turn 2: Cancel in Tanglish
    resp2 = await AssistantService.process_command(
        db_session,
        "Cancel pannidu, vendam",
        session_id=session_id
    )
    assert resp2.intent == "CANCELLATION"
    assert resp2.requires_confirmation is False
    assert SessionStore.get_pending_proposal(session_id) is None

    # Verify no stock was deducted (still 40)
    milk = seed_conversational_data["milk"]
    stock = await InventoryService.get_usable_stock(db_session, milk.id)
    assert stock == Decimal("40")


@pytest.mark.asyncio
async def test_conversational_spoken_confirmation_flow(db_session, seed_conversational_data):
    """
    Test proposal -> spoken confirmation:
    1. '2 milk packet vithuten' -> proposes sale.
    2. 'Aama confirm pannu' -> executes sale, stock deducted.
    """
    session_id = "test_confirm_flow"
    SessionStore.clear_session(session_id)

    # Turn 1: Propose sale
    resp1 = await AssistantService.process_command(
        db_session,
        "2 milk packet vithuten",
        session_id=session_id
    )
    assert resp1.intent == "RECORD_SALE"
    assert resp1.requires_confirmation is True

    # Turn 2: Spoken confirmation
    resp2 = await AssistantService.process_command(
        db_session,
        "Aama confirm pannu",
        session_id=session_id
    )
    assert resp2.intent == "RECORD_SALE"
    assert resp2.requires_confirmation is False
    assert "recorded successfully" in resp2.speech_text.lower() or "sale recorded" in resp2.speech_text.lower()

    # Verify stock deducted by 2 (40 -> 38)
    milk = seed_conversational_data["milk"]
    stock = await InventoryService.get_usable_stock(db_session, milk.id)
    assert stock == Decimal("38")


@pytest.mark.asyncio
async def test_conversational_correction_flow(db_session, seed_conversational_data):
    """
    Test proposal -> correction -> confirmation:
    1. 'Record a sale of 5 milk packets' -> proposes 5 packets.
    2. 'Illa, 5 illa 3 packet' -> updates proposal to 3 packets.
    3. 'Aama confirm pannu' -> executes sale for 3 packets. Stock: 40 -> 37.
    """
    session_id = "test_correction_flow"
    SessionStore.clear_session(session_id)

    # Turn 1: Propose 5 milk sale
    resp1 = await AssistantService.process_command(
        db_session,
        "Record a sale of 5 milk packets",
        session_id=session_id
    )
    assert resp1.intent == "RECORD_SALE"
    assert resp1.requires_confirmation is True
    pending1 = SessionStore.get_pending_proposal(session_id)
    assert pending1 is not None
    assert pending1["quantity"] == 5.0

    # Turn 2: Correction in Tanglish
    resp2 = await AssistantService.process_command(
        db_session,
        "Illa, 5 illa 3 packet",
        session_id=session_id
    )
    assert resp2.requires_confirmation is True
    pending2 = SessionStore.get_pending_proposal(session_id)
    assert pending2 is not None
    assert pending2["quantity"] == 3.0

    # Turn 3: Spoken confirmation
    resp3 = await AssistantService.process_command(
        db_session,
        "Aama confirm pannu",
        session_id=session_id
    )
    assert resp3.intent == "RECORD_SALE"
    assert resp3.requires_confirmation is False

    # Verify stock deducted by 3 (40 -> 37)
    milk = seed_conversational_data["milk"]
    stock = await InventoryService.get_usable_stock(db_session, milk.id)
    assert stock == Decimal("37")
