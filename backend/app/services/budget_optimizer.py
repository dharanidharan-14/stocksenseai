"""
StockSense AI - Budget-Aware Purchase Planner

Optimizes purchase allocation within a budget constraint using
a greedy priority-based approach.
"""

from decimal import Decimal
from typing import List, Optional
from math import ceil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.forecast import (
    ReorderRecommendation, BudgetPlan, BudgetPlanItem,
)
from app.models.supplier import Supplier


class BudgetOptimizer:
    """Budget-constrained purchase planner."""

    @staticmethod
    async def create_budget_plan(
        db: AsyncSession,
        budget_amount: Decimal,
        created_by=None,
    ) -> BudgetPlan:
        """
        Create a budget-aware purchase plan.
        
        Strategy:
        1. Get latest reorder recommendations
        2. Score each by priority (shortage severity, urgency)
        3. Sort by priority score descending
        4. Greedily allocate budget to highest-priority items
        5. Report included, excluded, and unmet demand
        """
        if budget_amount <= 0:
            raise ValueError("Budget must be positive")

        # Get latest reorder recommendations with suggested_quantity > 0
        result = await db.execute(
            select(ReorderRecommendation)
            .where(ReorderRecommendation.suggested_quantity > 0)
            .order_by(ReorderRecommendation.run_date.desc())
        )
        recommendations = result.scalars().all()

        if not recommendations:
            # No recommendations — create empty plan
            plan = BudgetPlan(
                budget_amount=budget_amount,
                total_allocated=Decimal("0"),
                remaining_budget=budget_amount,
                items_included=0,
                items_excluded=0,
                notes="No reorder recommendations found. Run forecast and reorder calculation first.",
                created_by=created_by,
            )
            db.add(plan)
            await db.flush()
            return plan

        # Deduplicate: keep only the latest recommendation per product
        latest_by_product = {}
        for rec in recommendations:
            if rec.product_id not in latest_by_product:
                latest_by_product[rec.product_id] = rec

        # Score and sort
        scored_items = []
        for rec in latest_by_product.values():
            product = await db.get(Product, rec.product_id)
            if not product or not product.is_active:
                continue

            score = BudgetOptimizer._calculate_priority_score(rec)

            # Get supplier min order constraints
            supplier = None
            if product.preferred_supplier_id:
                supplier = await db.get(Supplier, product.preferred_supplier_id)

            min_qty = Decimal("0")
            min_value = Decimal("0")
            if supplier:
                min_qty = supplier.min_order_quantity or Decimal("0")
                min_value = supplier.min_order_value or Decimal("0")

            # Apply minimum order quantity
            order_qty = rec.suggested_quantity
            if min_qty > 0 and order_qty < min_qty:
                order_qty = min_qty

            # Round up to whole units for discrete items
            if product.unit in ("packet", "piece", "bottle", "box"):
                order_qty = Decimal(str(ceil(float(order_qty))))

            line_cost = order_qty * product.purchase_cost

            scored_items.append({
                "rec": rec,
                "product": product,
                "score": score,
                "order_qty": order_qty,
                "unit_cost": product.purchase_cost,
                "line_cost": line_cost,
                "min_qty": min_qty,
                "min_value": min_value,
                "supplier": supplier,
            })

        # Sort by priority score (highest first)
        scored_items.sort(key=lambda x: x["score"], reverse=True)

        # Create budget plan
        plan = BudgetPlan(
            budget_amount=budget_amount,
            total_allocated=Decimal("0"),
            remaining_budget=budget_amount,
            items_included=0,
            items_excluded=0,
            created_by=created_by,
        )
        db.add(plan)
        await db.flush()

        remaining = budget_amount
        included_items = []
        excluded_items = []

        for item in scored_items:
            line_cost = item["line_cost"]

            if line_cost <= remaining:
                # Include this item
                plan_item = BudgetPlanItem(
                    budget_plan_id=plan.id,
                    product_id=item["product"].id,
                    suggested_quantity=item["order_qty"],
                    unit_cost=item["unit_cost"],
                    line_cost=line_cost,
                    priority=item["rec"].priority,
                    included=True,
                )
                db.add(plan_item)
                included_items.append(plan_item)
                remaining -= line_cost
            else:
                # Check if we can afford a partial order
                affordable_qty = remaining / item["unit_cost"] if item["unit_cost"] > 0 else Decimal("0")

                if item["product"].unit in ("packet", "piece", "bottle", "box"):
                    affordable_qty = Decimal(str(int(float(affordable_qty))))

                if affordable_qty >= item["min_qty"] and affordable_qty > 0:
                    partial_cost = affordable_qty * item["unit_cost"]
                    plan_item = BudgetPlanItem(
                        budget_plan_id=plan.id,
                        product_id=item["product"].id,
                        suggested_quantity=affordable_qty,
                        unit_cost=item["unit_cost"],
                        line_cost=partial_cost,
                        priority=item["rec"].priority,
                        included=True,
                    )
                    db.add(plan_item)
                    included_items.append(plan_item)
                    remaining -= partial_cost
                else:
                    # Exclude
                    exclusion_reason = f"Insufficient budget. Need ₹{line_cost:.2f}, only ₹{remaining:.2f} remaining."
                    if item["min_qty"] > 0 and affordable_qty < item["min_qty"]:
                        exclusion_reason += f" Minimum order quantity is {item['min_qty']}."

                    plan_item = BudgetPlanItem(
                        budget_plan_id=plan.id,
                        product_id=item["product"].id,
                        suggested_quantity=item["order_qty"],
                        unit_cost=item["unit_cost"],
                        line_cost=line_cost,
                        priority=item["rec"].priority,
                        included=False,
                        exclusion_reason=exclusion_reason,
                    )
                    db.add(plan_item)
                    excluded_items.append(plan_item)

        # Update plan totals
        plan.total_allocated = budget_amount - remaining
        plan.remaining_budget = remaining
        plan.items_included = len(included_items)
        plan.items_excluded = len(excluded_items)

        # Generate notes
        urgent_excluded = [
            e for e in excluded_items
            if e.priority in ("URGENT", "HIGH")
        ]
        if urgent_excluded:
            plan.notes = (
                f"⚠️ {len(urgent_excluded)} high-priority items could not be included "
                f"due to budget constraints. Consider increasing the budget."
            )
        else:
            plan.notes = (
                f"Budget plan created. {len(included_items)} items included, "
                f"₹{plan.total_allocated:.2f} allocated of ₹{budget_amount:.2f} budget."
            )

        await db.flush()
        return plan

    @staticmethod
    def _calculate_priority_score(rec: ReorderRecommendation) -> float:
        """
        Score a recommendation for budget prioritization.
        Higher score = higher priority for budget allocation.
        """
        score = 0.0

        # Priority weight (biggest factor)
        priority_weights = {"URGENT": 100, "HIGH": 70, "MEDIUM": 40, "LOW": 10}
        score += priority_weights.get(rec.priority, 0)

        # Shortage severity: how much of target is unmet
        if rec.target_stock and rec.target_stock > 0:
            shortage_ratio = float(
                (rec.target_stock - rec.inventory_position) / rec.target_stock
            )
            score += max(0, shortage_ratio * 30)

        # Stock urgency: lower stock = higher priority
        if rec.usable_stock is not None:
            if rec.usable_stock <= 0:
                score += 20  # Out of stock
            elif rec.lead_time_demand and rec.lead_time_demand > 0:
                coverage = float(rec.usable_stock / rec.lead_time_demand)
                if coverage < 1:
                    score += 15
                elif coverage < 2:
                    score += 5

        # Forecast confidence penalty
        if rec.forecast_confidence == "LOW":
            score *= 0.7  # Reduce priority for low-confidence forecasts

        return score
