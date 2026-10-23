"""
StockSense AI - Reliability, Intent Accuracy, and Anti-Hallucination Test Suite
Validates system behavior against hallucinations, out-of-boundary commands,
missing parameters, and product ambiguities.
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import date, timedelta
from app.services.assistant_service import AssistantService
from app.models.product import Product
from app.models.inventory import InventoryBatch
from app.services.session_store import SessionStore
from app.services.gemini_parser import GeminiParserService


@pytest_asyncio.fixture
async def seed_test_catalog(db_session):
    """Seed test catalog with multiple products, including similar names for ambiguity tests."""
    prod_amul = Product(
        name="Amul Taaza Toned Milk 500ml",
        sku="TEST-DAI-AMUL-01",
        unit="packet",
        purchase_cost=Decimal("24.00"),
        selling_price=Decimal("27.00"),
        reorder_threshold=Decimal("15"),
        safety_stock=Decimal("5"),
        is_active=True,
    )
    prod_aavin = Product(
        name="Aavin Green Full Cream Milk 500ml",
        sku="TEST-DAI-AAVIN-02",
        unit="packet",
        purchase_cost=Decimal("22.00"),
        selling_price=Decimal("25.00"),
        reorder_threshold=Decimal("15"),
        safety_stock=Decimal("5"),
        is_active=True,
    )
    prod_rice = Product(
        name="Ponni Boiled Rice 25kg",
        sku="TEST-GRN-RICE-01",
        unit="bag",
        purchase_cost=Decimal("1200.00"),
        selling_price=Decimal("1450.00"),
        reorder_threshold=Decimal("5"),
        safety_stock=Decimal("2"),
        is_active=True,
    )
    prod_dal = Product(
        name="Organic Moong Dal 1kg",
        sku="TEST-PUL-MOONG-01",
        unit="packet",
        purchase_cost=Decimal("110.00"),
        selling_price=Decimal("140.00"),
        reorder_threshold=Decimal("10"),
        safety_stock=Decimal("4"),
        is_active=True,
    )

    db_session.add_all([prod_amul, prod_aavin, prod_rice, prod_dal])
    await db_session.flush()

    today = date.today()
    batch_amul = InventoryBatch(
        product_id=prod_amul.id,
        batch_number="BAT-AMUL-01",
        received_quantity=Decimal("30"),
        remaining_quantity=Decimal("30"),
        unit_cost=Decimal("24.00"),
        expiry_date=today + timedelta(days=2),
        source_type="OPENING",
    )
    batch_dal = InventoryBatch(
        product_id=prod_dal.id,
        batch_number="BAT-DAL-01",
        received_quantity=Decimal("50"),
        remaining_quantity=Decimal("50"),
        unit_cost=Decimal("110.00"),
        expiry_date=today + timedelta(days=120),
        source_type="OPENING",
    )
    db_session.add_all([batch_amul, batch_dal])
    await db_session.commit()

    return {
        "amul": prod_amul,
        "aavin": prod_aavin,
        "rice": prod_rice,
        "dal": prod_dal,
    }


@pytest.mark.asyncio
async def test_remove_discount_offer_rejected_no_hallucination(db_session, seed_test_catalog):
    """
    Test Case: 'Remove the 20 percent offer on this product.'
    CRITICAL REQUIREMENT:
    - Must NOT hallucinate checking Moong Dal stock (from 'on' substring).
    - Must NOT claim discount was removed.
    - Must honestly report that discounts/offers are not supported in the schema.
    - 0 inventory or price mutations.
    """
    session_id = "test_discount_rejection"
    resp = await AssistantService.process_command(
        db_session,
        "Remove the 20 percent offer on this product.",
        session_id=session_id
    )

    # Validate intent and confidence status
    assert resp.intent == "DISCOUNT_OR_OFFER", f"Expected DISCOUNT_OR_OFFER, got {resp.intent}"
    assert resp.confidence_status == "UNSUPPORTED"
    assert resp.requires_confirmation is False
    assert resp.action_payload is None

    # Must explain that discount/offer management is not supported
    assert "discount" in resp.display_text.lower() or "offer" in resp.display_text.lower()
    assert "not supported" in resp.display_text.lower()

    # Must not contain Moong Dal or stock counts
    assert "moong" not in resp.display_text.lower()
    assert "usable stock" not in resp.display_text.lower()


@pytest.mark.asyncio
async def test_price_modification_rejected(db_session, seed_test_catalog):
    """
    Test Case: 'Change the price of rice to 50 rupees'
    Must reject direct price edits via voice, directing user to Product Management.
    """
    session_id = "test_price_rejection"
    resp = await AssistantService.process_command(
        db_session,
        "Change the price of rice to 50 rupees",
        session_id=session_id
    )

    assert resp.intent == "PRICE_MODIFICATION"
    assert resp.confidence_status == "UNSUPPORTED"
    assert resp.requires_confirmation is False
    assert "price" in resp.display_text.lower()
    assert "catalog" in resp.display_text.lower() or "management" in resp.display_text.lower()


@pytest.mark.asyncio
async def test_sale_missing_quantity_clarification(db_session, seed_test_catalog):
    """
    Test Case: 'Record a sale of moong dal' (No quantity specified!)
    CRITICAL REQUIREMENT:
    - Must NOT guess quantity 1 or 10.
    - Must ask for clarification with status NEEDS_CLARIFICATION.
    - Must not create pending confirmation with guessed numbers.
    """
    session_id = "test_sale_missing_qty"
    resp = await AssistantService.process_command(
        db_session,
        "Record a sale of moong dal",
        session_id=session_id
    )

    assert resp.intent == "CLARIFICATION", f"Expected CLARIFICATION, got {resp.intent}"
    assert resp.confidence_status == "NEEDS_CLARIFICATION"
    assert resp.requires_confirmation is False
    assert resp.action_payload is None
    # Must ask how many / how much
    assert "how many" in resp.display_text.lower() or "how much" in resp.display_text.lower() or "quantity" in resp.display_text.lower()


@pytest.mark.asyncio
async def test_stock_receipt_missing_quantity_clarification(db_session, seed_test_catalog):
    """
    Test Case: 'We received ponni boiled rice' (No quantity specified!)
    CRITICAL REQUIREMENT:
    - Must NOT guess quantity 10.
    - Must ask for clarification with status NEEDS_CLARIFICATION.
    """
    session_id = "test_rcpt_missing_qty"
    resp = await AssistantService.process_command(
        db_session,
        "We received ponni boiled rice",
        session_id=session_id
    )

    assert resp.intent == "CLARIFICATION", f"Expected CLARIFICATION, got {resp.intent}"
    assert resp.confidence_status == "NEEDS_CLARIFICATION"
    assert resp.requires_confirmation is False
    assert "quantity" in resp.display_text.lower() or "how many" in resp.display_text.lower() or "how much" in resp.display_text.lower()


@pytest.mark.asyncio
async def test_ambiguous_product_matching(db_session, seed_test_catalog):
    """
    Test Case: 'Check stock of milk'
    Both 'Amul Taaza Toned Milk' and 'Aavin Green Full Cream Milk' match 'milk'.
    Assistant must ask user to clarify which brand rather than picking one silently.
    """
    session_id = "test_ambiguity"
    resp = await AssistantService.process_command(
        db_session,
        "Check stock of milk",
        session_id=session_id
    )

    assert resp.intent == "CLARIFICATION"
    assert resp.confidence_status == "AMBIGUOUS"
    assert "amul" in resp.display_text.lower()
    assert "aavin" in resp.display_text.lower()


@pytest.mark.asyncio
async def test_unsupported_out_of_scope_query(db_session, seed_test_catalog):
    """
    Test Case: Non-inventory query: 'What is the capital of France?'
    Must NOT route into checking stock of any item in the store.
    """
    session_id = "test_out_of_scope"
    resp = await AssistantService.process_command(
        db_session,
        "What is the capital of France?",
        session_id=session_id
    )

    assert resp.intent in ("UNSUPPORTED", "UNKNOWN")
    assert resp.confidence_status == "UNSUPPORTED"
    assert "moong" not in resp.display_text.lower()
    assert "stock" not in resp.display_text.lower() or "inventory" in resp.display_text.lower()


@pytest.mark.asyncio
async def test_stop_words_do_not_match_products(db_session, seed_test_catalog):
    """
    Test that isolated stop words like 'on', 'the', 'this', 'product', 'offer'
    score 0 points in match_products and never trigger a random product hit.
    """
    # Matching against just 'on this product' should return no matches
    matches = await AssistantService.match_products(db_session, ["on this product"])
    assert len(matches) == 0, f"Expected 0 matches for stop words, got: {[p.name for p in matches]}"
