"""
StockSense AI - Smart Reorder Engine

Calculates reorder recommendations based on demand forecasts,
inventory positions, supplier lead times, and safety stock.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.forecast import DailyForecast, ForecastRun, ReorderRecommendation
from app.services.inventory_service import InventoryService
from app.services.purchase_service import PurchaseService


class ReorderEngine:
    """Calculates data-driven reorder recommendations."""

    @staticmethod
    async def calculate_recommendations(
        db: AsyncSession,
        product_ids: Optional[List[int]] = None,
    ) -> List[ReorderRecommendation]:
        """
        Calculate reorder recommendations for active products.
        
        Formula:
          lead_time_demand = forecast_demand_per_day × supplier_lead_time_days
          target_stock = lead_time_demand + safety_stock
          inventory_position = usable_on_hand + incoming_orders
          suggested_qty = max(0, target_stock - inventory_position)
        """
        today = date.today()
        now = datetime.now(timezone.utc)

        # Get active products
        query = select(Product).where(Product.is_active == True)
        if product_ids:
            query = query.where(Product.id.in_(product_ids))
        result = await db.execute(query)
        products = result.scalars().all()

        # Get latest forecast run
        latest_run = await db.execute(
            select(ForecastRun)
            .order_by(ForecastRun.created_at.desc())
            .limit(1)
        )
        forecast_run = latest_run.scalar_one_or_none()

        recommendations = []

        for product in products:
            # Get usable stock (exclude expired)
            usable_stock = await InventoryService.get_usable_stock(db, product.id, today)

            # Get incoming stock from open POs
            incoming_stock = await PurchaseService.get_incoming_stock(db, product.id)

            # Get forecast data
            daily_demand = Decimal("0")
            forecast_confidence = "LOW"

            if forecast_run:
                forecast_result = await db.execute(
                    select(DailyForecast)
                    .where(
                        DailyForecast.forecast_run_id == forecast_run.id,
                        DailyForecast.product_id == product.id,
                    )
                )
                forecasts = forecast_result.scalars().all()
                if forecasts:
                    total_demand = sum(f.predicted_demand for f in forecasts)
                    days = len(forecasts)
                    daily_demand = total_demand / days if days > 0 else Decimal("0")
                    forecast_confidence = forecasts[0].confidence or "LOW"

            # Calculate reorder quantities
            lead_time = product.supplier_lead_time_days or 3
            lead_time_demand = daily_demand * lead_time
            safety_stock = product.safety_stock or Decimal("0")
            target_stock = lead_time_demand + safety_stock
            inventory_position = usable_stock + incoming_stock
            suggested_qty = max(Decimal("0"), target_stock - inventory_position)

            # Round to reasonable units
            suggested_qty = Decimal(str(round(float(suggested_qty), 1)))

            # Calculate estimated cost
            estimated_cost = suggested_qty * product.purchase_cost

            # Determine priority
            priority = ReorderEngine._determine_priority(
                usable_stock=usable_stock,
                reorder_threshold=product.reorder_threshold,
                daily_demand=daily_demand,
                lead_time=lead_time,
                suggested_qty=suggested_qty,
                forecast_confidence=forecast_confidence,
            )

            # Generate explanation
            explanation = ReorderEngine._generate_explanation(
                product_name=product.name,
                usable_stock=usable_stock,
                incoming_stock=incoming_stock,
                daily_demand=daily_demand,
                lead_time=lead_time,
                safety_stock=safety_stock,
                target_stock=target_stock,
                inventory_position=inventory_position,
                suggested_qty=suggested_qty,
                priority=priority,
                forecast_confidence=forecast_confidence,
            )

            rec = ReorderRecommendation(
                product_id=product.id,
                run_date=now,
                usable_stock=usable_stock,
                incoming_stock=incoming_stock,
                lead_time_demand=lead_time_demand,
                safety_stock=safety_stock,
                target_stock=target_stock,
                inventory_position=inventory_position,
                suggested_quantity=suggested_qty,
                estimated_cost=estimated_cost,
                priority=priority,
                explanation=explanation,
                forecast_confidence=forecast_confidence,
            )
            db.add(rec)
            recommendations.append(rec)

        await db.flush()
        return recommendations

    @staticmethod
    def _determine_priority(
        usable_stock: Decimal,
        reorder_threshold: Decimal,
        daily_demand: Decimal,
        lead_time: int,
        suggested_qty: Decimal,
        forecast_confidence: str,
    ) -> str:
        """Assign priority based on transparent rules."""
        if suggested_qty <= 0:
            return "LOW"

        # Days of stock remaining
        if daily_demand > 0:
            days_remaining = float(usable_stock / daily_demand)
        else:
            days_remaining = float("inf")

        # URGENT: Will stock out before supplier can deliver
        if days_remaining < lead_time:
            return "URGENT"

        # HIGH: Below reorder threshold
        if usable_stock <= reorder_threshold:
            return "HIGH"

        # MEDIUM: Will need reorder within 2× lead time
        if days_remaining < lead_time * 2:
            return "MEDIUM"

        return "LOW"

    @staticmethod
    def _generate_explanation(
        product_name: str,
        usable_stock: Decimal,
        incoming_stock: Decimal,
        daily_demand: Decimal,
        lead_time: int,
        safety_stock: Decimal,
        target_stock: Decimal,
        inventory_position: Decimal,
        suggested_qty: Decimal,
        priority: str,
        forecast_confidence: str,
    ) -> str:
        """Generate a plain-language explanation of the recommendation."""
        parts = [f"Product: {product_name}"]
        parts.append(f"Current usable stock: {usable_stock}")
        parts.append(f"Incoming from open POs: {incoming_stock}")
        parts.append(f"Forecast daily demand: {daily_demand:.1f} (confidence: {forecast_confidence})")
        parts.append(f"Supplier lead time: {lead_time} days")
        parts.append(f"Lead-time demand: {daily_demand:.1f} × {lead_time} = {float(daily_demand * lead_time):.1f}")
        parts.append(f"Safety stock buffer: {safety_stock}")
        parts.append(f"Target stock level: {target_stock:.1f}")
        parts.append(f"Inventory position (on-hand + incoming): {inventory_position:.1f}")

        if suggested_qty > 0:
            parts.append(f"Suggested order: {suggested_qty} units")
            if priority == "URGENT":
                parts.append(
                    "⚠️ URGENT: Stock may run out before the supplier can deliver. "
                    "Place order immediately."
                )
            elif priority == "HIGH":
                parts.append("Stock is below reorder threshold. Reorder soon.")
        else:
            parts.append("No reorder needed — current inventory is sufficient.")

        if forecast_confidence == "LOW":
            parts.append(
                "Note: Forecast confidence is LOW due to limited sales history. "
                "This recommendation is an estimate — review before ordering."
            )

        return "\n".join(parts)
