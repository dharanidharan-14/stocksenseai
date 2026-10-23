"""
StockSense AI - Database Seeder Script

Populates the database with realistic Indian grocery store data:
- Admin and staff user accounts
- Categories (Grains, Pulses, Dairy, Spices, Snacks, etc.)
- Suppliers with realistic lead times and MOQs
- Products with realistic Indian FMCG prices, units, and shelf lives
- Multi-batch inventory with varying expiry dates (FEFO demonstration)
- 45 days of realistic daily sales history for forecasting and AI reordering
- Active and past Purchase Orders (incoming stock calculation)
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import random

from sqlalchemy import select
from app.core.database import async_engine, AsyncSessionLocal, Base
from app.core.security import hash_password
from app.models.user import User
from app.models.product import Category, Product
from app.models.supplier import Supplier
from app.models.inventory import InventoryBatch, StockMovement
from app.models.sale import Sale, SaleItem
from app.models.purchase import PurchaseOrder, PurchaseOrderItem


async def seed_database():
    print("[*] Starting StockSense AI database seeding...")

    # Create tables if they do not exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Tables verified/created")

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        result = await session.execute(select(User).where(User.email == "admin@stocksense.ai"))
        if result.scalar_one_or_none():
            print("[WARN] Database already seeded! Skipping.")
            return

        # 1. Users
        admin_user = User(
            email="admin@stocksense.ai",
            username="admin",
            hashed_password=hash_password("Admin@12345"),
            full_name="Ramesh Kumar (Store Owner)",
            is_active=True,
            is_superuser=True,
        )
        staff_user = User(
            email="staff@stocksense.ai",
            username="staff",
            hashed_password=hash_password("Staff@12345"),
            full_name="Priya Sharma (Store Associate)",
            is_active=True,
            is_superuser=False,
        )
        session.add_all([admin_user, staff_user])
        await session.flush()
        print("[OK] Created Users (admin@stocksense.ai, staff@stocksense.ai)")

        # 2. Categories
        cat_names = [
            ("Grains & Flours", "Staples including wheat atta, basmati rice, and maida"),
            ("Pulses & Dals", "Lentils and protein staples such as toor dal, moong dal"),
            ("Cooking Oils & Ghee", "Edible oils, refined sunflower oil, and pure cow ghee"),
            ("Dairy & Bakery", "Milk, butter, fresh paneer, and sandwich breads"),
            ("Spices & Masalas", "Indian spices, iodized salt, turmeric, and garam masala"),
            ("Snacks & Biscuits", "Instant noodles, biscuits, and packaged namkeens"),
            ("Beverages", "Premium tea, coffee powder, and health drinks"),
            ("Household & Cleaning", "Detergents, dishwashing bars, and personal care"),
        ]
        categories = {}
        for name, desc in cat_names:
            c = Category(name=name, description=desc)
            session.add(c)
            categories[name] = c
        await session.flush()
        print(f"[OK] Created {len(categories)} Categories")

        # 3. Suppliers
        suppliers_data = [
            {
                "name": "Sri Krishna FMCG Wholesalers",
                "contact_person": "Venkatesh Rao",
                "phone": "+91 98450 12345",
                "email": "orders@srikrishnafmcg.in",
                "address": "Shop 42, Wholesale APMC Market Yard, Bengaluru",
                "lead_time_days": 2,
                "min_order_quantity": Decimal("10"),
                "min_order_value": Decimal("4000.00"),
                "notes": "Fastest FMCG supplier for staples and packaged goods.",
            },
            {
                "name": "Annapurna Grain & Dal Millers",
                "contact_person": "Suresh Patel",
                "phone": "+91 98200 54321",
                "email": "suresh@annapurnagrains.com",
                "address": "Grain Merchant Street, Old City, Hyderabad",
                "lead_time_days": 4,
                "min_order_quantity": Decimal("25"),
                "min_order_value": Decimal("5000.00"),
                "notes": "Direct mill rates for pulses, rice and flours.",
            },
            {
                "name": "Om Shakti Fresh Dairy & Bakery",
                "contact_person": "Manoj Yadav",
                "phone": "+91 97110 98765",
                "email": "dispatch@omshaktidairy.com",
                "address": "Dairy Circle, Bengaluru",
                "lead_time_days": 1,
                "min_order_quantity": Decimal("5"),
                "min_order_value": Decimal("1000.00"),
                "notes": "Daily morning deliveries for fresh milk, bread, butter.",
            },
            {
                "name": "Balaji Spices & Edible Oils Ltd",
                "contact_person": "Chandresh Shah",
                "phone": "+91 99001 23456",
                "email": "chandresh@balajispices.co.in",
                "address": "Trade Center, APMC Market, Chennai",
                "lead_time_days": 3,
                "min_order_quantity": Decimal("15"),
                "min_order_value": Decimal("3500.00"),
                "notes": "Authorized distributor for Fortune, Amul Ghee, Tata Salt.",
            },
            {
                "name": "Hindustan Retail Logistics",
                "contact_person": "Deepak Verma",
                "phone": "+91 98190 67890",
                "email": "orders@hindustanretail.com",
                "address": "Central Warehouse Complex, Hosur Road",
                "lead_time_days": 5,
                "min_order_quantity": Decimal("20"),
                "min_order_value": Decimal("6000.00"),
                "notes": "Home care and personal hygiene products distributor.",
            },
        ]
        suppliers = []
        for s_data in suppliers_data:
            s = Supplier(**s_data)
            session.add(s)
            suppliers.append(s)
        await session.flush()
        print(f"[OK] Created {len(suppliers)} Suppliers")

        # 4. Products
        prods_info = [
            {
                "name": "Aashirvaad Shudh Chakki Atta 5kg",
                "sku": "GRN-ATTA-005",
                "category": categories["Grains & Flours"],
                "unit": "packet",
                "purchase_cost": Decimal("210.00"),
                "selling_price": Decimal("245.00"),
                "supplier": suppliers[1],
                "supplier_lead_time_days": 4,
                "safety_stock": Decimal("15.00"),
                "reorder_threshold": Decimal("25.00"),
                "shelf_life_days": 90,
            },
            {
                "name": "India Gate Basmati Rice Feast Rozzana 5kg",
                "sku": "GRN-RICE-005",
                "category": categories["Grains & Flours"],
                "unit": "packet",
                "purchase_cost": Decimal("380.00"),
                "selling_price": Decimal("440.00"),
                "supplier": suppliers[1],
                "supplier_lead_time_days": 4,
                "safety_stock": Decimal("10.00"),
                "reorder_threshold": Decimal("18.00"),
                "shelf_life_days": 365,
            },
            {
                "name": "Tata Salt Vacuum Evaporated Iodized 1kg",
                "sku": "SPC-SALT-001",
                "category": categories["Spices & Masalas"],
                "unit": "packet",
                "purchase_cost": Decimal("22.00"),
                "selling_price": Decimal("28.00"),
                "supplier": suppliers[3],
                "supplier_lead_time_days": 3,
                "safety_stock": Decimal("30.00"),
                "reorder_threshold": Decimal("45.00"),
                "shelf_life_days": 730,
            },
            {
                "name": "Fortune Sunlite Refined Sunflower Oil 1L Pouch",
                "sku": "OIL-SUN-001",
                "category": categories["Cooking Oils & Ghee"],
                "unit": "packet",
                "purchase_cost": Decimal("118.00"),
                "selling_price": Decimal("138.00"),
                "supplier": suppliers[3],
                "supplier_lead_time_days": 3,
                "safety_stock": Decimal("20.00"),
                "reorder_threshold": Decimal("32.00"),
                "shelf_life_days": 270,
            },
            {
                "name": "Amul Pure Ghee 1L Tin",
                "sku": "OIL-GHEE-001",
                "category": categories["Cooking Oils & Ghee"],
                "unit": "bottle",
                "purchase_cost": Decimal("565.00"),
                "selling_price": Decimal("640.00"),
                "supplier": suppliers[3],
                "supplier_lead_time_days": 3,
                "safety_stock": Decimal("8.00"),
                "reorder_threshold": Decimal("14.00"),
                "shelf_life_days": 270,
            },
            {
                "name": "Toor Dal Premium Unpolished 1kg",
                "sku": "PUL-TOOR-001",
                "category": categories["Pulses & Dals"],
                "unit": "kg",
                "purchase_cost": Decimal("142.00"),
                "selling_price": Decimal("168.00"),
                "supplier": suppliers[1],
                "supplier_lead_time_days": 4,
                "safety_stock": Decimal("18.00"),
                "reorder_threshold": Decimal("28.00"),
                "shelf_life_days": 180,
            },
            {
                "name": "Moong Dal Dhuli 1kg",
                "sku": "PUL-MOON-001",
                "category": categories["Pulses & Dals"],
                "unit": "kg",
                "purchase_cost": Decimal("112.00"),
                "selling_price": Decimal("132.00"),
                "supplier": suppliers[1],
                "supplier_lead_time_days": 4,
                "safety_stock": Decimal("12.00"),
                "reorder_threshold": Decimal("20.00"),
                "shelf_life_days": 180,
            },
            {
                "name": "Amul Taaza Homogenised Toned Milk 500ml",
                "sku": "DAY-MILK-001",
                "category": categories["Dairy & Bakery"],
                "unit": "packet",
                "purchase_cost": Decimal("25.50"),
                "selling_price": Decimal("28.00"),
                "supplier": suppliers[2],
                "supplier_lead_time_days": 1,
                "safety_stock": Decimal("35.00"),
                "reorder_threshold": Decimal("45.00"),
                "shelf_life_days": 2,
            },
            {
                "name": "Britannia 100% Whole Wheat Bread 400g",
                "sku": "DAY-BRED-001",
                "category": categories["Dairy & Bakery"],
                "unit": "packet",
                "purchase_cost": Decimal("42.00"),
                "selling_price": Decimal("50.00"),
                "supplier": suppliers[2],
                "supplier_lead_time_days": 1,
                "safety_stock": Decimal("15.00"),
                "reorder_threshold": Decimal("22.00"),
                "shelf_life_days": 5,
            },
            {
                "name": "Amul Butter Pasteurised 500g",
                "sku": "DAY-BUTR-500",
                "category": categories["Dairy & Bakery"],
                "unit": "packet",
                "purchase_cost": Decimal("248.00"),
                "selling_price": Decimal("285.00"),
                "supplier": suppliers[2],
                "supplier_lead_time_days": 1,
                "safety_stock": Decimal("10.00"),
                "reorder_threshold": Decimal("16.00"),
                "shelf_life_days": 180,
            },
            {
                "name": "Maggi 2-Minute Masala Instant Noodles 4-Pack",
                "sku": "SNK-MAGI-004",
                "category": categories["Snacks & Biscuits"],
                "unit": "packet",
                "purchase_cost": Decimal("48.00"),
                "selling_price": Decimal("56.00"),
                "supplier": suppliers[0],
                "supplier_lead_time_days": 2,
                "safety_stock": Decimal("40.00"),
                "reorder_threshold": Decimal("60.00"),
                "shelf_life_days": 270,
            },
            {
                "name": "Parle-G Gold Original Glucose Biscuits 1kg",
                "sku": "SNK-PARL-001",
                "category": categories["Snacks & Biscuits"],
                "unit": "packet",
                "purchase_cost": Decimal("85.00"),
                "selling_price": Decimal("100.00"),
                "supplier": suppliers[0],
                "supplier_lead_time_days": 2,
                "safety_stock": Decimal("20.00"),
                "reorder_threshold": Decimal("30.00"),
                "shelf_life_days": 180,
            },
            {
                "name": "Tata Tea Gold Leaf 500g",
                "sku": "BEV-TTEA-500",
                "category": categories["Beverages"],
                "unit": "packet",
                "purchase_cost": Decimal("295.00"),
                "selling_price": Decimal("340.00"),
                "supplier": suppliers[0],
                "supplier_lead_time_days": 2,
                "safety_stock": Decimal("12.00"),
                "reorder_threshold": Decimal("18.00"),
                "shelf_life_days": 365,
            },
            {
                "name": "Surf Excel Easy Wash Detergent Powder 1kg",
                "sku": "HSD-SURF-001",
                "category": categories["Household & Cleaning"],
                "unit": "packet",
                "purchase_cost": Decimal("125.00"),
                "selling_price": Decimal("148.00"),
                "supplier": suppliers[4],
                "supplier_lead_time_days": 5,
                "safety_stock": Decimal("15.00"),
                "reorder_threshold": Decimal("25.00"),
                "shelf_life_days": None,
            },
            {
                "name": "Vim Dishwash Bar with Lemon 300g",
                "sku": "HSD-VIMB-300",
                "category": categories["Household & Cleaning"],
                "unit": "piece",
                "purchase_cost": Decimal("26.00"),
                "selling_price": Decimal("32.00"),
                "supplier": suppliers[4],
                "supplier_lead_time_days": 5,
                "safety_stock": Decimal("25.00"),
                "reorder_threshold": Decimal("40.00"),
                "shelf_life_days": None,
            },
            {
                "name": "Everest Royal Garam Masala 100g Box",
                "sku": "SPC-GARM-100",
                "category": categories["Spices & Masalas"],
                "unit": "box",
                "purchase_cost": Decimal("76.00"),
                "selling_price": Decimal("92.00"),
                "supplier": suppliers[3],
                "supplier_lead_time_days": 3,
                "safety_stock": Decimal("8.00"),
                "reorder_threshold": Decimal("12.00"),
                "shelf_life_days": 365,
            },
        ]

        products = []
        for p_info in prods_info:
            p = Product(
                name=p_info["name"],
                sku=p_info["sku"],
                category_id=p_info["category"].id,
                unit=p_info["unit"],
                purchase_cost=p_info["purchase_cost"],
                selling_price=p_info["selling_price"],
                preferred_supplier_id=p_info["supplier"].id,
                supplier_lead_time_days=p_info["supplier_lead_time_days"],
                safety_stock=p_info["safety_stock"],
                reorder_threshold=p_info["reorder_threshold"],
                shelf_life_days=p_info["shelf_life_days"],
                is_active=True,
            )
            session.add(p)
            products.append(p)
        await session.flush()
        print(f"[OK] Created {len(products)} Products")


        # 6. Inventory Batches & Movements (FEFO Demonstration)
        today = date.today()
        batches = []
        movements = []

        batch_configs = [
            # Atta: 2 healthy batches
            {"prod_idx": 0, "batches": [
                {"batch": "BAT-ATTA-01", "qty": 20, "rem": 18, "mfg": today - timedelta(days=20), "exp": today + timedelta(days=70)},
                {"batch": "BAT-ATTA-02", "qty": 25, "rem": 25, "mfg": today - timedelta(days=5), "exp": today + timedelta(days=85)},
            ]},
            # Rice: 1 healthy batch
            {"prod_idx": 1, "batches": [
                {"batch": "BAT-RICE-01", "qty": 30, "rem": 24, "mfg": today - timedelta(days=30), "exp": today + timedelta(days=335)},
            ]},
            # Tata Salt: CRITICALLY LOW STOCK (4 units left, threshold 45) -> Triggers Urgent Reorder!
            {"prod_idx": 2, "batches": [
                {"batch": "BAT-SALT-01", "qty": 40, "rem": 4, "mfg": today - timedelta(days=60), "exp": today + timedelta(days=670)},
            ]},
            # Sunflower Oil: healthy batch
            {"prod_idx": 3, "batches": [
                {"batch": "BAT-SOIL-01", "qty": 35, "rem": 28, "mfg": today - timedelta(days=15), "exp": today + timedelta(days=255)},
            ]},
            # Amul Ghee: healthy
            {"prod_idx": 4, "batches": [
                {"batch": "BAT-GHEE-01", "qty": 15, "rem": 12, "mfg": today - timedelta(days=10), "exp": today + timedelta(days=260)},
            ]},
            # Toor Dal: 2 batches
            {"prod_idx": 5, "batches": [
                {"batch": "BAT-TOOR-01", "qty": 25, "rem": 8, "mfg": today - timedelta(days=40), "exp": today + timedelta(days=140)},
                {"batch": "BAT-TOOR-02", "qty": 20, "rem": 20, "mfg": today - timedelta(days=5), "exp": today + timedelta(days=175)},
            ]},
            # Moong Dal: 1 batch
            {"prod_idx": 6, "batches": [
                {"batch": "BAT-MOON-01", "qty": 20, "rem": 14, "mfg": today - timedelta(days=25), "exp": today + timedelta(days=155)},
            ]},
            # Milk: 1 URGENT EXPIRY (expiring tomorrow!), 1 fresh
            {"prod_idx": 7, "batches": [
                {"batch": "BAT-MILK-EXP", "qty": 15, "rem": 8, "mfg": today - timedelta(days=1), "exp": today + timedelta(days=1)},
                {"batch": "BAT-MILK-FRS", "qty": 30, "rem": 28, "mfg": today, "exp": today + timedelta(days=2)},
            ]},
            # Bread: 1 batch expiring in 2 days (urgent risk!), 1 fresh
            {"prod_idx": 8, "batches": [
                {"batch": "BAT-BRED-01", "qty": 12, "rem": 4, "mfg": today - timedelta(days=3), "exp": today + timedelta(days=2)},
                {"batch": "BAT-BRED-02", "qty": 20, "rem": 18, "mfg": today - timedelta(days=1), "exp": today + timedelta(days=4)},
            ]},
            # Amul Butter: 1 batch expiring in 20 days, 1 fresh
            {"prod_idx": 9, "batches": [
                {"batch": "BAT-BUTR-01", "qty": 15, "rem": 5, "mfg": today - timedelta(days=160), "exp": today + timedelta(days=20)},
                {"batch": "BAT-BUTR-02", "qty": 15, "rem": 14, "mfg": today - timedelta(days=10), "exp": today + timedelta(days=170)},
            ]},
            # Maggi: CRITICALLY LOW STOCK (7 units, threshold 60) -> Triggers Urgent Reorder!
            {"prod_idx": 10, "batches": [
                {"batch": "BAT-MAGI-01", "qty": 50, "rem": 7, "mfg": today - timedelta(days=45), "exp": today + timedelta(days=225)},
            ]},
            # Parle-G: good stock
            {"prod_idx": 11, "batches": [
                {"batch": "BAT-PARL-01", "qty": 30, "rem": 22, "mfg": today - timedelta(days=20), "exp": today + timedelta(days=160)},
            ]},
            # Tata Tea: good stock
            {"prod_idx": 12, "batches": [
                {"batch": "BAT-TTEA-01", "qty": 20, "rem": 15, "mfg": today - timedelta(days=15), "exp": today + timedelta(days=350)},
            ]},
            # Surf Excel: Non-perishable, healthy stock
            {"prod_idx": 13, "batches": [
                {"batch": "BAT-SURF-01", "qty": 25, "rem": 19, "mfg": today - timedelta(days=30), "exp": None},
            ]},
            # Vim Bar: Non-perishable, healthy stock
            {"prod_idx": 14, "batches": [
                {"batch": "BAT-VIMB-01", "qty": 40, "rem": 32, "mfg": today - timedelta(days=20), "exp": None},
            ]},
            # Garam Masala: Slow moving, steady stock
            {"prod_idx": 15, "batches": [
                {"batch": "BAT-GARM-01", "qty": 15, "rem": 11, "mfg": today - timedelta(days=40), "exp": today + timedelta(days=325)},
            ]},
        ]

        for item in batch_configs:
            p = products[item["prod_idx"]]
            for b_info in item["batches"]:
                batch = InventoryBatch(
                    product_id=p.id,
                    batch_number=b_info["batch"],
                    received_quantity=Decimal(str(b_info["qty"])),
                    remaining_quantity=Decimal(str(b_info["rem"])),
                    unit_cost=p.purchase_cost,
                    manufacture_date=b_info["mfg"],
                    expiry_date=b_info["exp"],
                    receipt_reference="INIT-OPENING-STOCK",
                    source_type="OPENING",
                )
                session.add(batch)
                batches.append(batch)
                await session.flush()

                # Record stock ledger movement
                mov = StockMovement(
                    product_id=p.id,
                    batch_id=batch.id,
                    movement_type="OPENING",
                    quantity=Decimal(str(b_info["qty"])),
                    reference_type="OPENING",
                    reference_id=batch.id,
                    notes=f"Initial stock initialization: batch {b_info['batch']}",
                )
                movements.append(mov)

                # If some quantity was already consumed in historical stock, record sale movement
                consumed = Decimal(str(b_info["qty"] - b_info["rem"]))
                if consumed > 0:
                    mov_consumed = StockMovement(
                        product_id=p.id,
                        batch_id=batch.id,
                        movement_type="SALE",
                        quantity=-consumed,
                        reference_type="SALE",
                        notes=f"Prior historical sales deduction for batch {b_info['batch']}",
                    )
                    movements.append(mov_consumed)

        session.add_all(movements)
        await session.flush()
        print(f"[OK] Created {len(batches)} Inventory Batches with FEFO and Expiry risks")

        # 7. 45 Days of Historical Sales (For AI Forecasting & Demand Analysis)
        print("[*] Generating 45 days of realistic sales history...")
        rng = random.Random(42)  # Deterministic seed for reproducible testing
        base_daily_rates = {
            0: 4.5,   # Atta: 4-5 packets/day
            1: 2.5,   # Rice: 2-3 packets/day
            2: 7.0,   # Tata Salt: 7 packets/day
            3: 5.0,   # Sunflower Oil: 5/day
            4: 1.2,   # Amul Ghee: 1-2/day
            5: 3.8,   # Toor Dal: 3-4 kg/day
            6: 2.2,   # Moong Dal: 2 kg/day
            7: 18.0,  # Milk: 18 packets/day (high volume!)
            8: 9.0,   # Bread: 9 packets/day
            9: 2.8,   # Butter: 2-3 packets/day
            10: 14.0, # Maggi: 14 packets/day (very high volume!)
            11: 6.0,  # Parle-G: 6/day
            12: 2.0,  # Tata Tea: 2/day
            13: 3.0,  # Surf Excel: 3/day
            14: 6.5,  # Vim Bar: 6-7/day
            15: 1.0,  # Garam Masala: 1/day
        }

        sales_created = 0
        sale_items_created = 0

        for day_offset in range(45, 0, -1):
            sale_day = today - timedelta(days=day_offset)
            weekday = sale_day.weekday()
            is_weekend = weekday in (5, 6)
            weekend_multiplier = 1.35 if is_weekend else 1.0

            # 2 to 4 sales transactions per day representing customer baskets
            num_txns = rng.randint(2, 4)
            for t_idx in range(num_txns):
                hour = rng.randint(9, 20)
                minute = rng.randint(0, 59)
                tx_time = datetime(sale_day.year, sale_day.month, sale_day.day, hour, minute, tzinfo=timezone.utc)

                # Select 2 to 5 random products for this customer transaction
                sampled_indices = rng.sample(range(len(products)), k=rng.randint(2, 5))
                total_sale_amt = Decimal("0")
                items_count = 0
                temp_items = []

                for p_idx in sampled_indices:
                    prod = products[p_idx]
                    base_rate = base_daily_rates[p_idx]
                    # Customer purchase portion
                    qty_float = max(1.0, round(rng.gauss(base_rate / num_txns * weekend_multiplier, 0.4)))
                    qty = Decimal(str(int(qty_float)))
                    line_total = (qty * prod.selling_price).quantize(Decimal("0.01"))

                    temp_items.append((prod.id, qty, prod.selling_price, line_total))
                    total_sale_amt += line_total
                    items_count += 1

                sale_rec = Sale(
                    sale_number=f"SAL-{sale_day.strftime('%Y%m%d')}-{t_idx+1:02d}",
                    sale_date=tx_time,
                    total_amount=total_sale_amt,
                    total_items=items_count,
                    reference_number=f"BILL-{day_offset}-{t_idx+1}",
                    status="COMPLETED",
                    notes="Counter walk-in customer sale",
                    is_historical_import=True,
                    affects_stock=False,  # Historical sales data for model training
                    created_by=admin_user.id,
                )
                session.add(sale_rec)
                await session.flush()
                sales_created += 1

                for p_id, q, price, ltot in temp_items:
                    s_item = SaleItem(
                        sale_id=sale_rec.id,
                        product_id=p_id,
                        quantity=q,
                        unit_price=price,
                        line_total=ltot,
                    )
                    session.add(s_item)
                    sale_items_created += 1

        await session.flush()
        print(f"[OK] Created {sales_created} Sales and {sale_items_created} Line Items across 45 days")

        # 8. Purchase Orders (Demonstrating Open & Incoming Stock)
        # PO 1: An ordered PO for Tata Salt & Maggi (incoming replenishment)
        po_open = PurchaseOrder(
            po_number="PO-2026-0001",
            supplier_id=suppliers[3].id,  # Balaji Spices
            order_date=today - timedelta(days=1),
            expected_delivery_date=today + timedelta(days=2),
            status="ORDERED",
            total_amount=Decimal("1100.00"),
            notes="Urgent replenishment for low stock Tata Salt",
            created_by=admin_user.id,
        )
        session.add(po_open)
        await session.flush()

        po_item1 = PurchaseOrderItem(
            purchase_order_id=po_open.id,
            product_id=products[2].id,  # Tata Salt
            ordered_quantity=Decimal("50.00"),
            received_quantity=Decimal("0.00"),
            unit_cost=products[2].purchase_cost,
            line_total=Decimal("1100.00"),
        )
        session.add(po_item1)

        # PO 2: A draft PO for Atta & Basmati Rice
        po_draft = PurchaseOrder(
            po_number="PO-2026-0002",
            supplier_id=suppliers[1].id,  # Annapurna
            order_date=today,
            expected_delivery_date=today + timedelta(days=4),
            status="DRAFT",
            total_amount=Decimal("8000.00"),
            notes="Weekly staples replenishment draft",
            created_by=admin_user.id,
        )
        session.add(po_draft)
        await session.flush()

        po_item2 = PurchaseOrderItem(
            purchase_order_id=po_draft.id,
            product_id=products[0].id,  # Atta
            ordered_quantity=Decimal("20.00"),
            received_quantity=Decimal("0.00"),
            unit_cost=products[0].purchase_cost,
            line_total=Decimal("4200.00"),
        )
        po_item3 = PurchaseOrderItem(
            purchase_order_id=po_draft.id,
            product_id=products[1].id,  # Basmati Rice
            ordered_quantity=Decimal("10.00"),
            received_quantity=Decimal("0.00"),
            unit_cost=products[1].purchase_cost,
            line_total=Decimal("3800.00"),
        )
        session.add_all([po_item2, po_item3])

        await session.commit()
        print("[OK] Created Purchase Orders (PO-2026-0001 [ORDERED], PO-2026-0002 [DRAFT])")
        print("\n[SUCCESS] StockSense AI database seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())
