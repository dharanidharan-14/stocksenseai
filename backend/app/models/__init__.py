"""
StockSense AI - Models Package

Import all models here so SQLAlchemy and Alembic can discover them.
"""

from app.models.user import User
from app.models.product import Category, Product
from app.models.supplier import Supplier
from app.models.inventory import InventoryBatch, StockMovement
from app.models.sale import Sale, SaleItem
from app.models.purchase import (
    PurchaseOrder, PurchaseOrderItem,
    PurchaseReceipt, PurchaseReceiptItem,
)
from app.models.forecast import (
    ForecastRun, DailyForecast,
    ReorderRecommendation, BudgetPlan, BudgetPlanItem,
    ImportJob,
)

__all__ = [
    "User",
    "Category",
    "Product",
    "Supplier",
    "InventoryBatch",
    "StockMovement",
    "Sale",
    "SaleItem",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseReceipt",
    "PurchaseReceiptItem",
    "ForecastRun",
    "DailyForecast",
    "ReorderRecommendation",
    "BudgetPlan",
    "BudgetPlanItem",
    "ImportJob",
]
