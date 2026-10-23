# StockSense AI — Architecture Document

## 1. System Overview

StockSense AI is a smart grocery inventory management system designed for small grocery shops in India. It helps shopkeepers monitor inventory, forecast demand, and make data-driven purchasing decisions.

**This is an internal shop management tool — not an e-commerce platform.**

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│                   React Frontend                     │
│  (Vite + TypeScript + Tailwind CSS + Recharts)       │
│                                                      │
│  Pages: Dashboard, Products, Inventory, Sales,       │
│         Suppliers, Purchase Orders, Expiry Manager,  │
│         AI Reorder Planner, Reports, Settings         │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/REST (Axios)
                       │ JWT Auth Headers
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                      │
│  (Python 3.11+ / Pydantic / SQLAlchemy 2.x)          │
│                                                      │
│  Routers: auth, products, inventory, sales,          │
│           suppliers, purchases, expiry, forecast,    │
│           reorder, budget, dashboard, reports         │
│                                                      │
│  Services: inventory_service, sales_service,         │
│            purchase_service, forecast_engine,         │
│            reorder_engine, budget_optimizer           │
└──────────────────────┬──────────────────────────────┘
                       │ SQLAlchemy ORM
                       │ Alembic Migrations
┌──────────────────────▼──────────────────────────────┐
│               PostgreSQL Database                    │
│                                                      │
│  Tables: users, products, suppliers,                 │
│          product_suppliers, inventory_batches,        │
│          stock_movements, sales, sale_items,          │
│          purchase_orders, purchase_order_items,       │
│          purchase_receipts, purchase_receipt_items,   │
│          forecast_runs, daily_forecasts,              │
│          reorder_recommendations, budget_plans,       │
│          budget_plan_items, categories                │
└─────────────────────────────────────────────────────┘
```

## 3. Key Design Decisions

### 3.1 Stock Accounting: Batch-Based Ledger

Stock is tracked via **inventory batches** and a **stock movement ledger**. There is no single editable "quantity" field on the product. The authoritative stock count is derived from:

- Sum of `remaining_quantity` across active, non-expired batches

Every stock change (receipt, sale, adjustment, damage, correction) creates a `stock_movement` record, providing a complete audit trail.

### 3.2 FEFO (First Expiry, First Out)

When consuming stock for sales, the system selects batches with the **earliest expiry date** first. Non-expiring batches are consumed after all expiring batches. This minimizes waste.

### 3.3 Decimal Precision for Currency

All monetary values use `Decimal` / `NUMERIC(12,2)` in PostgreSQL — never floating-point — to prevent rounding errors in financial calculations.

### 3.4 Transaction Safety

Multi-step operations (sales, purchase receipts, stock adjustments) use database transactions. If any step fails, the entire operation rolls back. Row-level locking (`SELECT ... FOR UPDATE`) prevents concurrent overselling.

### 3.5 Forecasting Architecture

The forecasting engine is a standalone Python module (`backend/app/forecasting/`), not embedded in API routes. It:

1. Aggregates daily sales data per product
2. Applies a moving-average baseline
3. Attempts Holt-Winters exponential smoothing when sufficient data exists
4. Falls back gracefully with confidence labeling
5. Uses chronological backtesting (no future data leakage)

### 3.6 Reorder Engine

The reorder engine computes:
```
lead_time_demand = forecast_demand × supplier_lead_time_days
target_stock = lead_time_demand + safety_stock
inventory_position = usable_on_hand + incoming_orders - reserved
suggested_qty = max(0, target_stock - inventory_position)
```

Expired batches are excluded. Expiry-at-risk stock is discounted. Each recommendation includes a plain-language explanation.

### 3.7 Budget Optimizer

Uses a greedy-priority approach to allocate a rupee budget across products:
1. Score each product by shortage severity, stockout urgency, forecast confidence
2. Sort by priority score
3. Allocate budget to highest-priority items first
4. Respect minimum order quantities and unit rounding
5. Report unmet demand separately

## 4. Major Workflows

### 4.1 Product Creation
`POST /api/products` → validate fields → check SKU uniqueness → insert → return

### 4.2 Stock Receipt (from Purchase Order)
`POST /api/purchase-orders/{id}/receive` → validate PO status → for each line item:
  → create inventory_batch → create stock_movement (type=RECEIPT)
  → update PO line received_qty → update PO status
All within a single DB transaction.

### 4.3 Sale Recording
`POST /api/sales` → validate products/quantities → for each line item:
  → query eligible batches (FEFO order, non-expired, remaining > 0)
  → consume from batches → create stock_movements (type=SALE)
  → create sale + sale_items
All within a single DB transaction. Fails if insufficient stock.

### 4.4 Forecast Generation
`POST /api/forecast/run` → for each active product:
  → aggregate historical daily sales
  → determine data sufficiency
  → select model (moving average vs Holt-Winters)
  → generate forecasts → store forecast_run + daily_forecasts

### 4.5 Reorder Calculation
`POST /api/reorder/recalculate` → for each active product:
  → get latest forecast → compute lead-time demand
  → compute usable stock (exclude expired)
  → compute incoming stock from open POs
  → calculate suggested order quantity
  → assign priority → store recommendations

## 5. Security

- JWT-based authentication (access tokens)
- Passwords hashed with bcrypt
- Protected endpoints require valid JWT
- No sensitive data in responses
- Environment variables for secrets (.env)

## 6. API Documentation

FastAPI auto-generates OpenAPI (Swagger) docs at `/docs` and `/redoc`.
