"""
Test suite for Product Image Upload, Validation, and Serving
"""

import pytest
import io
from fastapi import UploadFile
from app.services.inventory_service import InventoryService
from app.models.product import Product


@pytest.mark.asyncio
async def test_product_image_schema_field(db_session):
    """Test that Product model and schema support image_url."""
    prod = Product(
        name="Test Image Product 1kg",
        sku="TEST-IMG-001",
        unit="packet",
        purchase_cost=50.0,
        selling_price=60.0,
        image_url="/uploads/products/test.png",
        is_active=True,
    )
    db_session.add(prod)
    await db_session.flush()

    assert prod.id is not None
    assert prod.image_url == "/uploads/products/test.png"


@pytest.mark.asyncio
async def test_product_image_upload_endpoint(client, test_user):
    """Test POST /api/products/{id}/image with valid and invalid files."""
    headers = test_user["headers"]
    # 1. Create a product
    create_payload = {
        "name": "Upload Test Milk 500ml",
        "sku": f"TEST-UP-MILK-{id(client)}",
        "unit": "packet",
        "purchase_cost": 25.0,
        "selling_price": 30.0,
        "is_active": True,
    }
    res = await client.post("/api/products", json=create_payload, headers=headers)
    assert res.status_code == 201
    prod_id = res.json()["id"]

    # 2. Upload invalid MIME type (e.g. text/plain)
    files_invalid = {"file": ("test.txt", io.BytesIO(b"plain text content"), "text/plain")}
    res_bad = await client.post(f"/api/products/{prod_id}/image", files=files_invalid, headers=headers)
    assert res_bad.status_code == 400
    assert "Invalid image type" in res_bad.json()["detail"]

    # 3. Upload valid PNG image
    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files_valid = {"file": ("milk.png", io.BytesIO(tiny_png), "image/png")}
    res_ok = await client.post(f"/api/products/{prod_id}/image", files=files_valid, headers=headers)
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["image_url"] is not None
    assert data["image_url"].startswith(f"/uploads/products/prod_{prod_id}_")

    # 4. Verify get_product returns the same image_url
    get_res = await client.get(f"/api/products/{prod_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["image_url"] == data["image_url"]

    # 5. Delete product image
    del_res = await client.delete(f"/api/products/{prod_id}/image", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["image_url"] is None
