"""
Strict Senior Engineer Verification Test Suite
Tests live FastAPI server + PostgreSQL backend against requirements:
1. Product creation
2. Opening stock / stock receipt
3. Sale deduction & FEFO batch consumption
4. Partial purchase receipts & full receipt lifecycle
5. Stock movement audit ledger history
6. Database constraints & duplicate stock verification
"""

import sys
import json
import urllib.request
import urllib.error
from datetime import date, timedelta

BASE_URL = "http://127.0.0.1:8000/api"

def request(method, path, data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            return response.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = err_body
        return e.code, parsed

def run_tests():
    print("=" * 60)
    print("STARTING STRICT VERIFICATION SUITE")
    print("=" * 60)
    
    # 1. Authentication
    print("\n[TEST 1] Authenticating as admin...")
    status, res = request("POST", "/auth/login", {"email": "admin@stocksense.ai", "password": "Admin@12345"})
    assert status == 200, f"Login failed: {res}"
    token = res["access_token"]
    print("  -> Auth successful. Token obtained.")

    # 2. Product Creation
    print("\n[TEST 2] Product Creation...")
    import time
    test_sku = f"TEST-SKU-{int(time.time())}"
    prod_payload = {
        "name": "Strict Test Organic Ghee 500ml",
        "sku": test_sku,
        "category_id": 3,
        "unit": "bottle",
        "purchase_cost": 320.0,
        "selling_price": 380.0,
        "preferred_supplier_id": 4,
        "supplier_lead_time_days": 3,
        "safety_stock": 10.0,
        "reorder_threshold": 20.0,
        "shelf_life_days": 180,
    }
    status, prod = request("POST", "/products", prod_payload, token)
    assert status == 201, f"Product creation failed: {prod}"
    product_id = prod["id"]
    print(f"  -> Product created with ID {product_id}, SKU: {prod['sku']}")

    # Test SKU duplicate constraint
    status, dup_err = request("POST", "/products", prod_payload, token)
    assert status == 400, f"Expected 400 on duplicate SKU, got {status}: {dup_err}"
    print(f"  -> Duplicate SKU properly rejected with 400: {dup_err.get('detail')}")

    # 3. Opening Stock & Stock Receipts
    print("\n[TEST 3] Creating Multiple Batches for FEFO Testing...")
    # Batch 1: Expiring in 10 days
    expiry_near = (date.today() + timedelta(days=10)).isoformat()
    rcpt1_payload = {
        "product_id": product_id,
        "quantity": 15.0,
        "unit_cost": 320.0,
        "batch_number": f"BATCH-NEAR-{int(time.time())}",
        "expiry_date": expiry_near,
        "source_type": "OPENING",
        "notes": "Opening stock near expiry",
    }
    status, batch1 = request("POST", "/inventory/receipts", rcpt1_payload, token)
    assert status == 201, f"Receipt 1 failed: {batch1}"
    b1_id = batch1["id"]
    print(f"  -> Batch 1 (Near: expires {expiry_near}) created: 15 units, ID {b1_id}")

    # Batch 2: Expiring in 60 days
    expiry_far = (date.today() + timedelta(days=60)).isoformat()
    rcpt2_payload = {
        "product_id": product_id,
        "quantity": 25.0,
        "unit_cost": 320.0,
        "batch_number": f"BATCH-FAR-{int(time.time())}",
        "expiry_date": expiry_far,
        "source_type": "DIRECT_RECEIPT",
        "notes": "Direct receipt far expiry",
    }
    status, batch2 = request("POST", "/inventory/receipts", rcpt2_payload, token)
    assert status == 201, f"Receipt 2 failed: {batch2}"
    b2_id = batch2["id"]
    print(f"  -> Batch 2 (Far: expires {expiry_far}) created: 25 units, ID {b2_id}")

    # Verify product stock levels
    status, prod_check = request("GET", f"/products/{product_id}", token=token)
    assert status == 200
    assert float(prod_check["current_stock"]) == 40.0, f"Expected 40.0 current stock, got {prod_check.get('current_stock')}"
    print(f"  -> Total usable stock verified: {prod_check['current_stock']} units")

    # 4. FEFO Consumption via Sale
    print("\n[TEST 4] Sale Deduction & FEFO Consumption...")
    # Sell 20 units: should consume ALL 15 from Batch 1 (expires in 10 days) and 5 from Batch 2 (expires in 60 days)
    sale_payload = {
        "items": [
            {
                "product_id": product_id,
                "quantity": 20.0,
                "unit_price": 380.0,
            }
        ],
        "notes": "Strict FEFO verification sale",
    }
    status, sale = request("POST", "/sales", sale_payload, token)
    assert status == 201, f"Sale creation failed: {sale}"
    print(f"  -> Sale created: {sale['sale_number']}, Total: {sale['total_amount']}")

    # Verify Batch 1 remaining quantity
    status, b1_check = request("GET", f"/inventory/batches/{b1_id}", token=token)
    assert status == 200
    assert float(b1_check["remaining_quantity"]) == 0.0, f"Batch 1 should be 0.0, got {b1_check['remaining_quantity']}"
    print(f"  -> Batch 1 (Near Expiry) correctly consumed to 0: remaining = {b1_check['remaining_quantity']}")

    # Verify Batch 2 remaining quantity (25 - 5 = 20)
    status, b2_check = request("GET", f"/inventory/batches/{b2_id}", token=token)
    assert status == 200
    assert float(b2_check["remaining_quantity"]) == 20.0, f"Batch 2 should have 20.0 remaining, got {b2_check['remaining_quantity']}"
    print(f"  -> Batch 2 (Far Expiry) correctly consumed 5 units: remaining = {b2_check['remaining_quantity']}")

    # 5. Purchase Order Lifecycle & Partial Receipt
    print("\n[TEST 5] Purchase Order Lifecycle & Partial Receipt...")
    po_payload = {
        "supplier_id": 4,
        "items": [
            {
                "product_id": product_id,
                "ordered_quantity": 50.0,
                "unit_cost": 315.0,
            }
        ],
        "notes": "Strict verification PO",
    }
    status, po = request("POST", "/purchase-orders", po_payload, token)
    assert status == 201, f"PO creation failed: {po}"
    po_id = po["id"]
    po_item_id = po["items"][0]["id"]
    assert po["status"] == "DRAFT"
    print(f"  -> PO created: #{po['po_number']}, status = {po['status']}")

    # Confirm PO
    status, po_confirmed = request("POST", f"/purchase-orders/{po_id}/confirm", token=token)
    assert status == 200, f"Confirm PO failed: {status} -> {po_confirmed}"
    assert po_confirmed["status"] == "ORDERED"
    print(f"  -> PO confirmed: status = {po_confirmed['status']}")

    # Partial Receipt: Receive 20 of 50
    partial_rcpt_payload = {
        "receipt_date": date.today().isoformat(),
        "notes": "First partial receipt (20 units)",
        "items": [
            {
                "purchase_order_item_id": po_item_id,
                "quantity_received": 20.0,
                "unit_cost": 315.0,
                "batch_number": "BATCH-PO-PARTIAL-1",
                "expiry_date": (date.today() + timedelta(days=120)).isoformat(),
            }
        ],
    }
    status, rcv1 = request("POST", f"/purchase-orders/{po_id}/receive", partial_rcpt_payload, token)
    assert status == 200, f"Partial receive failed: {rcv1}"
    print(f"  -> Partial receipt recorded: #{rcv1['receipt_number']}")

    # Check PO status is PARTIALLY_RECEIVED
    status, po_part = request("GET", f"/purchase-orders/{po_id}", token=token)
    assert status == 200
    assert po_part["status"] == "PARTIALLY_RECEIVED", f"Expected PARTIALLY_RECEIVED, got {po_part['status']}"
    assert float(po_part["items"][0]["received_quantity"]) == 20.0
    assert float(po_part["items"][0]["remaining_quantity"]) == 30.0
    print(f"  -> PO status verified: {po_part['status']} (received: {po_part['items'][0]['received_quantity']}, remaining: {po_part['items'][0]['remaining_quantity']})")

    # Complete Receipt: Receive remaining 30 units
    final_rcpt_payload = {
        "receipt_date": date.today().isoformat(),
        "notes": "Second final receipt (30 units)",
        "items": [
            {
                "purchase_order_item_id": po_item_id,
                "quantity_received": 30.0,
                "unit_cost": 315.0,
                "batch_number": "BATCH-PO-FINAL-2",
                "expiry_date": (date.today() + timedelta(days=120)).isoformat(),
            }
        ],
    }
    status, rcv2 = request("POST", f"/purchase-orders/{po_id}/receive", final_rcpt_payload, token)
    assert status == 200, f"Final receive failed: {rcv2}"

    # Check PO status is now RECEIVED
    status, po_full = request("GET", f"/purchase-orders/{po_id}", token=token)
    assert status == 200
    assert po_full["status"] == "RECEIVED", f"Expected RECEIVED, got {po_full['status']}"
    assert float(po_full["items"][0]["received_quantity"]) == 50.0
    assert float(po_full["items"][0]["remaining_quantity"]) == 0.0
    print(f"  -> PO full receipt verified: status = {po_full['status']} (received 50/50)")

    # 6. Stock Movement History Audit Ledger
    print("\n[TEST 6] Stock Movement History Audit Ledger...")
    status, movements = request("GET", f"/inventory/movements?product_id={product_id}", token=token)
    assert status == 200
    print(f"  -> Stock movements recorded for product {product_id}: {movements['total']} entries")
    for m in movements["items"]:
        print(f"     Movement ID {m['id']}: type={m['movement_type']}, qty={m['quantity']}, ref={m.get('reference_type')}, notes={m.get('notes')}")

    print("\n" + "=" * 60)
    print("ALL CORE INVENTORY, FEFO, SALE, AND PO TESTS PASSED EMPIRICALLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
