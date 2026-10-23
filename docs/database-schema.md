# Database Schema — StockSense AI

## Entity-Relationship Overview

### Core Entities
- **users** — Application users (shop staff)
- **categories** — Product categories
- **products** — Grocery items tracked by the shop
- **suppliers** — Vendors who supply products
- **product_suppliers** — Many-to-many product↔supplier relationships

### Inventory
- **inventory_batches** — Individual stock batches with expiry tracking
- **stock_movements** — Audit log of every stock change

### Sales
- **sales** — Sale transaction headers
- **sale_items** — Individual line items within a sale

### Purchasing
- **purchase_orders** — Purchase order headers
- **purchase_order_items** — Line items on a PO
- **purchase_receipts** — Receipt events against a PO
- **purchase_receipt_items** — Line items received in a receipt

### AI & Planning
- **forecast_runs** — Metadata for each forecast execution
- **daily_forecasts** — Per-product daily demand predictions
- **reorder_recommendations** — Calculated reorder suggestions
- **budget_plans** — Budget-constrained purchase plans
- **budget_plan_items** — Items within a budget plan

### System
- **import_jobs** — Tracking CSV import operations

## Table Definitions

### users
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| username | VARCHAR(100) | UNIQUE, NOT NULL |
| hashed_password | VARCHAR(255) | NOT NULL |
| full_name | VARCHAR(200) | |
| is_active | BOOLEAN | DEFAULT TRUE |
| is_superuser | BOOLEAN | DEFAULT FALSE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### categories
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| name | VARCHAR(100) | UNIQUE, NOT NULL |
| description | TEXT | |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### products
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| name | VARCHAR(200) | NOT NULL |
| sku | VARCHAR(50) | UNIQUE, NOT NULL |
| category_id | INTEGER | FK → categories.id |
| unit | VARCHAR(20) | NOT NULL (packet, piece, kg, g, litre, ml, bottle, box) |
| purchase_cost | NUMERIC(12,2) | NOT NULL, >= 0 |
| selling_price | NUMERIC(12,2) | NOT NULL, >= 0 |
| preferred_supplier_id | INTEGER | FK → suppliers.id, nullable |
| supplier_lead_time_days | INTEGER | DEFAULT 3 |
| safety_stock | NUMERIC(10,2) | DEFAULT 0 |
| reorder_threshold | NUMERIC(10,2) | DEFAULT 0 |
| shelf_life_days | INTEGER | nullable (NULL = non-perishable) |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### suppliers
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| name | VARCHAR(200) | NOT NULL |
| contact_person | VARCHAR(200) | |
| phone | VARCHAR(20) | |
| email | VARCHAR(255) | |
| address | TEXT | |
| lead_time_days | INTEGER | DEFAULT 3 |
| min_order_quantity | NUMERIC(10,2) | nullable |
| min_order_value | NUMERIC(12,2) | nullable |
| notes | TEXT | |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### inventory_batches
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| product_id | INTEGER | FK → products.id, NOT NULL |
| batch_number | VARCHAR(100) | nullable |
| received_quantity | NUMERIC(10,2) | NOT NULL, > 0 |
| remaining_quantity | NUMERIC(10,2) | NOT NULL, >= 0 |
| unit_cost | NUMERIC(12,2) | NOT NULL |
| manufacture_date | DATE | nullable |
| expiry_date | DATE | nullable |
| receipt_reference | VARCHAR(100) | nullable |
| source_type | VARCHAR(30) | NOT NULL (PURCHASE, OPENING, ADJUSTMENT) |
| source_id | INTEGER | nullable (PO receipt item ID, etc.) |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

Index: (product_id, expiry_date) for FEFO queries

### stock_movements
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| product_id | INTEGER | FK → products.id, NOT NULL |
| batch_id | INTEGER | FK → inventory_batches.id, nullable |
| movement_type | VARCHAR(30) | NOT NULL |
| quantity | NUMERIC(10,2) | NOT NULL (positive=in, negative=out) |
| reference_type | VARCHAR(30) | nullable (SALE, PURCHASE, ADJUSTMENT, etc.) |
| reference_id | INTEGER | nullable |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

movement_type values: RECEIPT, SALE, ADJUSTMENT, DAMAGE, CORRECTION, OPENING, REVERSAL

### sales
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| sale_number | VARCHAR(50) | UNIQUE |
| sale_date | TIMESTAMPTZ | NOT NULL |
| total_amount | NUMERIC(12,2) | NOT NULL |
| total_items | INTEGER | NOT NULL |
| reference_number | VARCHAR(100) | nullable |
| status | VARCHAR(20) | DEFAULT 'COMPLETED' |
| notes | TEXT | |
| created_by | UUID | FK → users.id |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

status: COMPLETED, CANCELLED

### sale_items
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| sale_id | INTEGER | FK → sales.id, NOT NULL |
| product_id | INTEGER | FK → products.id, NOT NULL |
| quantity | NUMERIC(10,2) | NOT NULL, > 0 |
| unit_price | NUMERIC(12,2) | NOT NULL |
| line_total | NUMERIC(12,2) | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### purchase_orders
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| po_number | VARCHAR(50) | UNIQUE, NOT NULL |
| supplier_id | INTEGER | FK → suppliers.id, NOT NULL |
| order_date | DATE | NOT NULL |
| expected_delivery_date | DATE | nullable |
| status | VARCHAR(30) | DEFAULT 'DRAFT' |
| total_amount | NUMERIC(12,2) | DEFAULT 0 |
| notes | TEXT | |
| created_by | UUID | FK → users.id |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

status: DRAFT, ORDERED, PARTIALLY_RECEIVED, RECEIVED, CANCELLED

### purchase_order_items
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| purchase_order_id | INTEGER | FK → purchase_orders.id, NOT NULL |
| product_id | INTEGER | FK → products.id, NOT NULL |
| ordered_quantity | NUMERIC(10,2) | NOT NULL, > 0 |
| received_quantity | NUMERIC(10,2) | DEFAULT 0 |
| unit_cost | NUMERIC(12,2) | NOT NULL |
| line_total | NUMERIC(12,2) | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### purchase_receipts
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| purchase_order_id | INTEGER | FK → purchase_orders.id, NOT NULL |
| receipt_number | VARCHAR(50) | UNIQUE, NOT NULL |
| receipt_date | DATE | NOT NULL |
| notes | TEXT | |
| created_by | UUID | FK → users.id |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### purchase_receipt_items
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| purchase_receipt_id | INTEGER | FK → purchase_receipts.id, NOT NULL |
| purchase_order_item_id | INTEGER | FK → purchase_order_items.id, NOT NULL |
| product_id | INTEGER | FK → products.id, NOT NULL |
| quantity_received | NUMERIC(10,2) | NOT NULL, > 0 |
| unit_cost | NUMERIC(12,2) | NOT NULL |
| batch_number | VARCHAR(100) | nullable |
| manufacture_date | DATE | nullable |
| expiry_date | DATE | nullable |
| batch_id | INTEGER | FK → inventory_batches.id (created during receipt) |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### forecast_runs
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| run_date | TIMESTAMPTZ | NOT NULL |
| horizon_days | INTEGER | NOT NULL |
| model_used | VARCHAR(50) | |
| parameters | JSONB | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### daily_forecasts
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| forecast_run_id | INTEGER | FK → forecast_runs.id, NOT NULL |
| product_id | INTEGER | FK → products.id, NOT NULL |
| forecast_date | DATE | NOT NULL |
| predicted_demand | NUMERIC(10,2) | NOT NULL |
| lower_bound | NUMERIC(10,2) | nullable |
| upper_bound | NUMERIC(10,2) | nullable |
| model_used | VARCHAR(50) | |
| confidence | VARCHAR(20) | (HIGH, MEDIUM, LOW) |
| mae | NUMERIC(10,4) | nullable |
| wape | NUMERIC(10,4) | nullable |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### reorder_recommendations
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| product_id | INTEGER | FK → products.id, NOT NULL |
| run_date | TIMESTAMPTZ | NOT NULL |
| usable_stock | NUMERIC(10,2) | |
| incoming_stock | NUMERIC(10,2) | |
| lead_time_demand | NUMERIC(10,2) | |
| safety_stock | NUMERIC(10,2) | |
| target_stock | NUMERIC(10,2) | |
| inventory_position | NUMERIC(10,2) | |
| suggested_quantity | NUMERIC(10,2) | |
| estimated_cost | NUMERIC(12,2) | |
| priority | VARCHAR(20) | (URGENT, HIGH, MEDIUM, LOW) |
| explanation | TEXT | |
| forecast_confidence | VARCHAR(20) | |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### budget_plans
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| budget_amount | NUMERIC(12,2) | NOT NULL |
| total_allocated | NUMERIC(12,2) | DEFAULT 0 |
| remaining_budget | NUMERIC(12,2) | DEFAULT 0 |
| items_included | INTEGER | DEFAULT 0 |
| items_excluded | INTEGER | DEFAULT 0 |
| notes | TEXT | |
| created_by | UUID | FK → users.id |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### budget_plan_items
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| budget_plan_id | INTEGER | FK → budget_plans.id, NOT NULL |
| product_id | INTEGER | FK → products.id, NOT NULL |
| suggested_quantity | NUMERIC(10,2) | NOT NULL |
| unit_cost | NUMERIC(12,2) | NOT NULL |
| line_cost | NUMERIC(12,2) | NOT NULL |
| priority | VARCHAR(20) | |
| included | BOOLEAN | NOT NULL |
| exclusion_reason | TEXT | nullable |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

### import_jobs
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, SERIAL |
| job_type | VARCHAR(50) | NOT NULL (PRODUCTS, SALES) |
| file_name | VARCHAR(255) | |
| status | VARCHAR(30) | (PENDING, PROCESSING, COMPLETED, FAILED) |
| total_rows | INTEGER | |
| processed_rows | INTEGER | |
| error_rows | INTEGER | |
| errors | JSONB | |
| created_by | UUID | FK → users.id |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| completed_at | TIMESTAMPTZ | |
