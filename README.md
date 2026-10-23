# StockSense AI — Smart Grocery Inventory Management System

A comprehensive inventory management system designed for small grocery shops in India. Features AI-powered demand forecasting, smart reorder recommendations, budget-aware purchase planning, and batch-level inventory tracking with FEFO (First Expiry, First Out) support.

## Features

- **Product Management** — Full CRUD with SKU uniqueness, unit validation, category & supplier associations
- **Batch Inventory Tracking** — FEFO-based stock consumption with full audit ledger (`stock_movements`)
- **POS Counter Sales** — Real-time billing with automated FEFO batch deductions and reversal capability
- **Supplier Management** — Profiles with lead time tracking and minimum order thresholds
- **Purchase Orders** — Complete Draft → Ordered → Partial/Full Receipt lifecycle with batch creation
- **Expiry Risk Manager** — Batch-level monitoring, days-to-expiry categorization, and loss estimation
- **AI Demand Forecasting** — Multi-model selection (Moving Average + Holt-Winters) with backtest validation
- **Smart Reorder Engine** — Calculates safety stock, lead time demand, and urgency priority levels
- **Budget Optimizer** — Greedy priority-based purchase optimizer respecting working capital limits
- **Reports** — Sales history, stock levels, and purchase history reporting

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, TypeScript, Vite, Vanilla CSS + Tailwind tokens, Lucide Icons |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0 (AsyncIO), Pydantic v2 |
| **Database** | PostgreSQL 15+ (`asyncpg` for async FastAPI engine, `psycopg` for sync Alembic/Seed) |
| **AI/ML** | Statsmodels, NumPy, Pandas |
| **Authentication** | JWT (HS256) + bcrypt password hashing |

---

## Prerequisites

- **Python 3.11+** (Verified on Python 3.14.2)
- **Node.js 18+** & npm
- **PostgreSQL 14+** (running locally on port 1234 or 5432)

---

## Exact Working Setup Instructions

### 1. Database Configuration

Create the database in PostgreSQL:
```sql
CREATE DATABASE stocksense_ai;
```

Configure `backend/.env` (and root `.env`):
```ini
APP_NAME=StockSense AI
DEBUG=True
SECRET_KEY=stocksense-ai-super-secret-key-change-in-production-2026
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Replace user, password, host, and port with your PostgreSQL setup
DATABASE_URL=postgresql+asyncpg://postgres:0000@localhost:1234/stocksense_ai
DATABASE_URL_SYNC=postgresql+psycopg://postgres:0000@localhost:1234/stocksense_ai

CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000
DEFAULT_SAFETY_STOCK_DAYS=7
DEFAULT_LEAD_TIME_DAYS=3
```

### 2. Backend Installation & Migrations

```bash
cd backend

# Install dependencies (including asyncpg and psycopg)
pip install -r requirements.txt
pip install "psycopg[binary]" asyncpg

# Run Alembic migrations to create all 19 PostgreSQL tables
alembic upgrade head

# Seed initial store data (users, categories, suppliers, products, batches, sales, POs)
python -m app.seed
```

### 3. Start Backend Server

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation available at:
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 4. Frontend Installation & Startup

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
Access the web application at: [http://127.0.0.1:5173](http://127.0.0.1:5173)

---

## Seeded Credentials

| Role | Email | Password |
|---|---|---|
| **Store Owner (Admin)** | `admin@stocksense.ai` | `Admin@12345` |
| **Cashier / Staff** | `cashier@stocksense.ai` | `Cashier@12345` |

The frontend automatically validates authentication on connection check using these credentials.

---

## Running Automated & Empirical Tests

### Automated Unit & Integration Tests (pytest)
```bash
cd backend
python -m pytest tests/ -v
```
*Current result: 15 passed in ~3.6s.*

### Strict End-to-End Verification Test (Live Database)
Tests product creation, opening stock, FEFO batch consumption via sale, partial PO receipts, full PO receipts, and the movement audit ledger:
```bash
cd backend
python tests/test_strict_verification.py
```
*Current result: ALL 6 test suites passed empirically against live PostgreSQL.*

---

## Project Structure

```
stocksense-ai/
├── backend/
│   ├── alembic/                 # Database schema migrations
│   │   ├── versions/            # Versioned migration scripts
│   │   └── env.py               # Async Alembic runner
│   ├── app/
│   │   ├── api/                 # API route controllers
│   │   │   ├── auth.py          # JWT login and registration
│   │   │   ├── products.py      # Product catalog & categories
│   │   │   ├── inventory.py     # Batches, receipts & stock movements
│   │   │   ├── sales.py         # POS sales & FEFO deductions
│   │   │   ├── purchases.py     # PO lifecycle & receipt processing
│   │   │   ├── suppliers.py     # Supplier directory
│   │   │   └── forecast.py      # AI forecasting, reorder & budget
│   │   ├── core/                # DB engine, config & security
│   │   ├── models/              # SQLAlchemy 2.0 ORM entities
│   │   ├── schemas/             # Pydantic v2 schemas
│   │   ├── services/            # Core business logic services
│   │   └── forecasting/         # Moving average & Holt-Winters engine
│   ├── tests/                   # Pytest & live verification test suites
│   ├── alembic.ini              # Alembic configuration
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # Header, Sidebar, MetricCards, etc.
│   │   ├── pages/               # Dashboard, POS, Reorder, Expiry, Inventory, POs
│   │   ├── services/api.ts      # Axios client with auto-auth & endpoints
│   │   └── types.ts             # TypeScript entity definitions
│   ├── package.json
│   └── vite.config.ts
├── .env.example                 # Environment template
└── README.md                    # System documentation
```

---

## License

Private — Built for small grocery shops in India.
