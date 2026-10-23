"""
StockSense AI - API Endpoints Integration Tests
"""

import pytest
from decimal import Decimal
from app.models.product import Category, Product


@pytest.mark.asyncio
async def test_auth_login_endpoint(client, test_user):
    # Test valid credentials
    response = await client.post(
        "/api/auth/login",
        json={"email": "testuser@stocksense.ai", "password": "Test@12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "testuser@stocksense.ai"

    # Test invalid password
    bad_resp = await client.post(
        "/api/auth/login",
        json={"email": "testuser@stocksense.ai", "password": "WrongPassword"},
    )
    assert bad_resp.status_code == 401


@pytest.mark.asyncio
async def test_products_crud(client, test_user, db_session):
    headers = test_user["headers"]

    # 1. Create a category
    cat_resp = await client.post(
        "/api/products/categories",
        headers=headers,
        json={"name": "Grains & Cereals", "description": "Wheat, rice, and millets"},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    # 2. Create a product
    prod_resp = await client.post(
        "/api/products",
        headers=headers,
        json={
            "name": "Organic Chakki Atta 10kg",
            "sku": "GRN-ATTA-010",
            "category_id": cat_id,
            "unit": "packet",
            "purchase_cost": 410.0,
            "selling_price": 480.0,
            "safety_stock": 10.0,
            "reorder_threshold": 15.0,
            "shelf_life_days": 90,
        },
    )
    assert prod_resp.status_code == 201
    prod_data = prod_resp.json()
    assert prod_data["sku"] == "GRN-ATTA-010"
    prod_id = prod_data["id"]

    # 3. List products
    list_resp = await client.get("/api/products", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(p["id"] == prod_id for p in items)

    # 4. Get product detail
    detail_resp = await client.get(f"/api/products/{prod_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["name"] == "Organic Chakki Atta 10kg"


@pytest.mark.asyncio
async def test_inventory_stock_receipt_and_summary(client, test_user, db_session):
    headers = test_user["headers"]

    # Setup category and product
    cat = Category(name="Oils")
    db_session.add(cat)
    await db_session.flush()

    prod = Product(
        name="Groundnut Oil 1L",
        sku="OIL-GND-001",
        category_id=cat.id,
        unit="packet",
        purchase_cost=Decimal("150.00"),
        selling_price=Decimal("175.00"),
    )
    db_session.add(prod)
    await db_session.commit()

    # Receive stock via API
    receipt_resp = await client.post(
        "/api/inventory/receipts",
        headers=headers,
        json={
            "product_id": prod.id,
            "quantity": 25.0,
            "unit_cost": 150.0,
            "batch_number": "BATCH-GND-101",
            "source_type": "DIRECT_RECEIPT",
            "notes": "Direct wholesale stock addition",
        },
    )
    assert receipt_resp.status_code == 201

    # Check inventory summary
    summary_resp = await client.get("/api/inventory/summary", headers=headers)
    assert summary_resp.status_code == 200
    summary_items = summary_resp.json()["items"]
    matching = [item for item in summary_items if item["product_id"] == prod.id]
    assert len(matching) == 1
    assert Decimal(str(matching[0]["usable_stock"])) == Decimal("25.00")
    assert Decimal(str(matching[0]["total_stock"])) == Decimal("25.00")


@pytest.mark.asyncio
async def test_purchase_order_lifecycle_and_partial_receipt(client, test_user, db_session):
    from app.models.supplier import Supplier
    from datetime import date
    headers = test_user["headers"]

    # 1. Create supplier & product
    sup = Supplier(name="Test Wholesaler", lead_time_days=2, is_active=True)
    db_session.add(sup)
    await db_session.flush()

    prod = Product(
        name="Basmati Super 5kg",
        sku="RIC-BAS-099",
        unit="packet",
        purchase_cost=Decimal("300.00"),
        selling_price=Decimal("360.00"),
        preferred_supplier_id=sup.id,
    )
    db_session.add(prod)
    await db_session.commit()

    # 2. Create Purchase Order (Draft)
    po_resp = await client.post(
        "/api/purchase-orders",
        headers=headers,
        json={
            "supplier_id": sup.id,
            "items": [
                {
                    "product_id": prod.id,
                    "ordered_quantity": 40.0,
                    "unit_cost": 300.0,
                }
            ],
            "notes": "Test PO lifecycle",
        },
    )
    assert po_resp.status_code == 201
    po_data = po_resp.json()
    assert po_data["status"] == "DRAFT"
    po_id = po_data["id"]
    po_item_id = po_data["items"][0]["id"]

    # 3. Confirm Purchase Order
    confirm_resp = await client.post(f"/api/purchase-orders/{po_id}/confirm", headers=headers)
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "ORDERED"

    # 4. Partial receipt: Receive 15 out of 40
    rcv1_resp = await client.post(
        f"/api/purchase-orders/{po_id}/receive",
        headers=headers,
        json={
            "items": [
                {
                    "purchase_order_item_id": po_item_id,
                    "quantity_received": 15.0,
                    "unit_cost": 300.0,
                    "batch_number": "BAT-PARTIAL-1",
                }
            ],
        },
    )
    assert rcv1_resp.status_code == 200

    # Verify PO status is PARTIALLY_RECEIVED
    po_part = (await client.get(f"/api/purchase-orders/{po_id}", headers=headers)).json()
    assert po_part["status"] == "PARTIALLY_RECEIVED"
    assert Decimal(str(po_part["items"][0]["received_quantity"])) == Decimal("15.00")
    assert Decimal(str(po_part["items"][0]["remaining_quantity"])) == Decimal("25.00")

    # 5. Full receipt: Receive remaining 25
    rcv2_resp = await client.post(
        f"/api/purchase-orders/{po_id}/receive",
        headers=headers,
        json={
            "items": [
                {
                    "purchase_order_item_id": po_item_id,
                    "quantity_received": 25.0,
                    "unit_cost": 300.0,
                    "batch_number": "BAT-FINAL-2",
                }
            ],
        },
    )
    assert rcv2_resp.status_code == 200

    # Verify PO status is now RECEIVED
    po_full = (await client.get(f"/api/purchase-orders/{po_id}", headers=headers)).json()
    assert po_full["status"] == "RECEIVED"
    assert Decimal(str(po_full["items"][0]["received_quantity"])) == Decimal("40.00")
    assert Decimal(str(po_full["items"][0]["remaining_quantity"])) == Decimal("0.00")


@pytest.mark.asyncio
async def test_sales_fefo_consumption_and_movements(client, test_user, db_session):
    from datetime import date, timedelta
    headers = test_user["headers"]

    prod = Product(
        name="FEFO Test Tea 250g",
        sku="BEV-TEA-777",
        unit="packet",
        purchase_cost=Decimal("70.00"),
        selling_price=Decimal("95.00"),
    )
    db_session.add(prod)
    await db_session.commit()

    # Receive batch expiring in 5 days
    exp_near = (date.today() + timedelta(days=5)).isoformat()
    r1 = await client.post(
        "/api/inventory/receipts",
        headers=headers,
        json={
            "product_id": prod.id,
            "quantity": 10.0,
            "unit_cost": 70.0,
            "batch_number": "BAT-TEA-NEAR",
            "expiry_date": exp_near,
        },
    )
    assert r1.status_code == 201
    b1_id = r1.json()["id"]

    # Receive batch expiring in 50 days
    exp_far = (date.today() + timedelta(days=50)).isoformat()
    r2 = await client.post(
        "/api/inventory/receipts",
        headers=headers,
        json={
            "product_id": prod.id,
            "quantity": 20.0,
            "unit_cost": 70.0,
            "batch_number": "BAT-TEA-FAR",
            "expiry_date": exp_far,
        },
    )
    assert r2.status_code == 201
    b2_id = r2.json()["id"]

    # Make sale of 15 units (should exhaust batch 1 of 10, and take 5 from batch 2)
    sale_resp = await client.post(
        "/api/sales",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": prod.id,
                    "quantity": 15.0,
                    "unit_price": 95.0,
                }
            ],
            "notes": "FEFO sale test",
        },
    )
    assert sale_resp.status_code == 201

    # Verify batch balances
    b1 = (await client.get(f"/api/inventory/batches/{b1_id}", headers=headers)).json()
    b2 = (await client.get(f"/api/inventory/batches/{b2_id}", headers=headers)).json()
    assert Decimal(str(b1["remaining_quantity"])) == Decimal("0.00")
    assert Decimal(str(b2["remaining_quantity"])) == Decimal("15.00")

    # Verify stock movements audit ledger
    moves_resp = await client.get(f"/api/inventory/movements?product_id={prod.id}", headers=headers)
    assert moves_resp.status_code == 200
    moves = moves_resp.json()["items"]
    assert len(moves) == 4  # 2 receipts + 2 sale deductions
    sale_moves = [m for m in moves if m["movement_type"] == "SALE"]
    assert len(sale_moves) == 2
    assert sorted([float(m["quantity"]) for m in sale_moves]) == [-15.0, -5.0] or sorted([abs(float(m["quantity"])) for m in sale_moves]) == [5.0, 10.0]


@pytest.mark.asyncio
async def test_forecast_dashboard_stats_endpoint(client, test_user):
    headers = test_user["headers"]
    resp = await client.get("/api/forecast/dashboard/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_products" in data
    assert "total_inventory_value" in data
    assert "sales_trend" in data
    assert "top_selling_products" in data
    assert isinstance(data["sales_trend"], list)

