"""
StockSense AI - Voice Assistant Service

Integrates Gemini AI natural language understanding with PostgreSQL inventory models,
FEFO batch allocation, and sales/receipt transactions.
Supports English, Tamil, Tanglish, local Kirana slang, and multi-turn corrections.
"""

import re
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.inventory import InventoryBatch, StockMovement
from app.models.sale import Sale, SaleItem
from app.models.supplier import Supplier
from app.models.forecast import ReorderRecommendation, ForecastRun
from app.schemas.sale import SaleItemCreate
from app.schemas.assistant import (
    AssistantResponse,
    StockInfo,
    BatchInfo,
    SaleSummaryData,
    ReorderItem,
    ProductMatch,
    GeminiParsedIntent,
)
from app.services.inventory_service import InventoryService
from app.services.sales_service import SalesService
from app.services.reorder_engine import ReorderEngine
from app.services.budget_optimizer import BudgetOptimizer
from app.services.gemini_parser import GeminiParserService
from app.services.session_store import SessionStore

logger = logging.getLogger("stocksense.assistant")

# Common Tamil and regional colloquial aliases mapped to grocery keywords
REGIONAL_ALIASES: Dict[str, str] = {
    "thakkali": "tomato",
    "paal": "milk",
    "arisi": "rice",
    "aata": "atta",
    "atta": "atta",
    "gothumai": "atta",
    "ghee": "ghee",
    "nei": "ghee",
    "venkayam": "onion",
    "vengayam": "onion",
    "paruppu": "dal",
    "dhal": "dal",
    "toor": "toor dal",
    "moong": "moong dal",
    "uppu": "salt",
    "oil": "oil",
    "ennai": "oil",
    "sunflower": "sunflower",
    "biscuit": "biscuit",
    "bread": "bread",
    "rotti": "bread",
    "tea": "tea",
    "chaaya": "tea",
    "coffee": "coffee",
    "detergent": "surf",
    "surf": "surf",
    "soap": "soap",
    "maggi": "maggi",
    "noodles": "maggi",
    "butter": "butter",
    "masala": "masala",
}


def parse_number_from_text(text: str) -> Optional[Decimal]:
    """Helper to extract quantity numbers from text."""
    cleaned = text.replace(",", "")
    match = re.search(r"\b(\d+(?:\.\d+)?)\b", cleaned)
    if match:
        try:
            return Decimal(match.group(1))
        except Exception:
            pass
    return None


class AssistantService:
    """Service that coordinates Gemini NLU, conversational context, and PostgreSQL inventory operations."""

    @classmethod
    async def match_products(
        cls,
        db: AsyncSession,
        search_terms: List[str],
    ) -> List[Product]:
        """
        Fuzzy matches products against actual database records using normalized terms,
        raw terms, and regional aliases.
        """
        result = await db.execute(select(Product).where(Product.is_active == True))
        all_products = result.scalars().all()

        # Build candidate keyword tokens
        tokens = set()
        for term in search_terms:
            if not term:
                continue
            t_clean = term.lower().strip()
            # Check regional alias table
            if t_clean in REGIONAL_ALIASES:
                tokens.add(REGIONAL_ALIASES[t_clean])
            for word in re.findall(r"\b[a-zA-Z0-9]+\b", t_clean):
                if len(word) >= 2:
                    tokens.add(word)
                    if word in REGIONAL_ALIASES:
                        tokens.add(REGIONAL_ALIASES[word])

        if not tokens:
            return []

        scored_matches = []
        for p in all_products:
            p_name_lower = p.name.lower()
            p_sku_lower = p.sku.lower()
            score = 0
            for token in tokens:
                if token in p_name_lower:
                    score += 3 if len(token) > 3 else 1
                if token in p_sku_lower:
                    score += 2
            if score > 0:
                scored_matches.append((p, score))

        scored_matches.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored_matches]

    @classmethod
    async def process_command(
        cls,
        db: AsyncSession,
        command_text: str,
        confirmed: bool = False,
        action_payload: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> AssistantResponse:
        """
        Main entrypoint:
        1. Checks for direct UI confirmation button payloads.
        2. Retrieves session context history.
        3. Parses semantic intent via Gemini LLM.
        4. Handles cancellations, confirmations, and multi-turn corrections.
        5. Executes database reads or prepares transactional mutation previews.
        """
        text = command_text.strip()
        session_id = session_id or "default_session"

        # ─── 1. DIRECT CONFIRMATION CALLBACK (FROM UI BUTTON) ───
        if confirmed and action_payload:
            resp = await cls._execute_confirmed_action(db, action_payload)
            SessionStore.clear_pending_proposal(session_id)
            SessionStore.append_turn(session_id, "assistant", resp.speech_text)
            return resp

        # Append user turn to session history
        if text:
            SessionStore.append_turn(session_id, "user", text)

        # ─── 2. GEMINI SEMANTIC NLU PARSING ───
        context_history = SessionStore.get_context_history(session_id)
        parsed = await GeminiParserService.parse_intent(text, context_history=context_history)

        # ─── 3. MULTI-TURN CONVERSATION: CANCELLATION ───
        if parsed.is_cancellation or parsed.intent == "CANCELLATION":
            SessionStore.clear_pending_proposal(session_id)
            speech = parsed.spoken_reply_tamil or parsed.spoken_reply_english or "Transaction cancelled."
            display = "❌ **Transaction Cancelled.** No changes were made to inventory or sales ledgers."
            resp = AssistantResponse(
                intent="CANCELLATION",
                speech_text=speech,
                display_text=display,
                suggestions=["How much rice stock is left?", "What should I reorder today?"]
            )
            SessionStore.append_turn(session_id, "assistant", resp.speech_text)
            return resp

        # ─── 4. MULTI-TURN CONVERSATION: SPOKEN CONFIRMATION ("Aama", "Confirm", "Yes") ───
        if parsed.is_confirmation or parsed.intent == "CONFIRMATION":
            pending = SessionStore.get_pending_proposal(session_id)
            if pending:
                resp = await cls._execute_confirmed_action(db, pending)
                SessionStore.clear_pending_proposal(session_id)
                SessionStore.append_turn(session_id, "assistant", resp.speech_text)
                return resp
            else:
                resp = AssistantResponse(
                    intent="CONFIRMATION",
                    speech_text="There is no pending transaction to confirm. What would you like to do?",
                    display_text="No pending proposal found. You can ask to record a sale or receive new stock.",
                    suggestions=["How much rice stock is left?", "Record a sale of 2 milk packets"]
                )
                SessionStore.append_turn(session_id, "assistant", resp.speech_text)
                return resp

        # ─── 5. MULTI-TURN CONVERSATION: CORRECTION ("Illa, 5 illa 3 packet") ───
        if parsed.is_correction or parsed.intent == "CORRECTION":
            pending = SessionStore.get_pending_proposal(session_id)
            if pending:
                # Update quantity or details
                if parsed.quantity is not None:
                    pending["quantity"] = float(parsed.quantity)
                if parsed.unit:
                    pending["unit"] = parsed.unit

                # Recalculate totals
                if pending["action"] == "RECORD_SALE":
                    unit_price = Decimal(str(pending["unit_price"]))
                    qty = Decimal(str(pending["quantity"]))
                    pending["line_total"] = float(qty * unit_price)
                
                SessionStore.set_pending_proposal(session_id, pending)

                speech = (
                    f"Updated to {pending['quantity']} {pending['unit']} of {pending['product_name']}. "
                    f"Please confirm to complete."
                )
                display = (
                    f"### Updated Proposal (Revision Acknowledged)\n"
                    f"- **Action:** {pending['action'].replace('_', ' ')}\n"
                    f"- **Product:** {pending['product_name']}\n"
                    f"- **Revised Quantity:** {pending['quantity']} {pending['unit']}\n"
                )
                if pending["action"] == "RECORD_SALE":
                    display += f"- **Revised Amount:** ₹{pending['line_total']:,.2f}\n"

                display += f"\n*Do you want to confirm and proceed with this revised transaction?*"

                resp = AssistantResponse(
                    intent=pending["action"],
                    speech_text=speech,
                    display_text=display,
                    requires_confirmation=True,
                    action_payload=pending,
                    data=pending,
                    suggestions=["Aama, confirm pannu", "Cancel pannidu"]
                )
                SessionStore.append_turn(session_id, "assistant", resp.speech_text)
                return resp

        # ─── 6. ROUTE BASED ON GEMINI PARSED INTENT ───
        intent = parsed.intent

        if intent == "CHECK_STOCK":
            resp = await cls._handle_check_stock(db, text, parsed)
        elif intent == "CHECK_LOW_STOCK":
            resp = await cls._handle_low_stock(db, parsed)
        elif intent == "CHECK_OUT_OF_STOCK":
            resp = await cls._handle_out_of_stock(db, parsed)
        elif intent == "CHECK_EXPIRY":
            resp = await cls._handle_expiry_queries(db, text, parsed)
        elif intent == "SALES_INFO":
            resp = await cls._handle_sales_info(db, text, parsed)
        elif intent == "AI_RECOMMENDATION":
            resp = await cls._handle_reorder_recommendations(db, text, parsed)
        elif intent == "RECORD_SALE":
            resp = await cls._handle_record_sale(db, text, parsed, session_id)
        elif intent == "RECEIVE_STOCK":
            resp = await cls._handle_receive_stock(db, text, parsed, session_id)
        else:
            # Fallback product match check
            search_candidates = [parsed.product_normalized, parsed.product_raw, text]
            matched = await cls.match_products(db, [c for c in search_candidates if c])
            if matched:
                resp = await cls._handle_check_stock(db, text, parsed)
            else:
                resp = AssistantResponse(
                    intent="UNKNOWN",
                    speech_text=parsed.spoken_reply_tamil or parsed.spoken_reply_english or "I did not quite understand that. You can ask about stock, sales, or expiry.",
                    display_text=(
                        "I couldn't identify the requested operation. "
                        "You can speak or type in English, Tamil, or Tanglish. Try one of the suggestions below:"
                    ),
                    suggestions=[
                        "Tomato stock la evlo irukku?",
                        "Innaiku sales evlo?",
                        "Naalaiku expire aagura items enna?",
                        "What should I reorder today?",
                        "Record a sale of 2 milk packets",
                    ],
                )

        SessionStore.append_turn(session_id, "assistant", resp.speech_text)
        return resp

    # ──────────────────────────────────────────────────────────────────────────
    # A. READ-ONLY INVENTORY QUERIES
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_check_stock(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        search_terms = [parsed.product_normalized, parsed.product_raw, text]
        matched = await cls.match_products(db, [t for t in search_terms if t])

        if not matched:
            spoken = parsed.spoken_reply_tamil or parsed.spoken_reply_english or "No matching product found in inventory."
            return AssistantResponse(
                intent="CHECK_STOCK",
                speech_text=spoken,
                display_text=f"No product found matching '{parsed.product_raw or parsed.product_normalized or text}' in database. Please check the spelling or catalog.",
                suggestions=["Show all products currently out of stock", "Which products are running low?"]
            )

        # Ambiguity check: If user asks generically and multiple distinct top brands match
        if len(matched) > 1 and not (parsed.product_raw and parsed.product_raw.lower() in matched[0].name.lower()):
            first_two = matched[:2]
            p1_name = first_two[0].name
            p2_name = first_two[1].name
            if parsed.product_normalized and parsed.product_normalized.lower() not in p1_name.lower():
                speech = f"Did you mean {p1_name} or {p2_name}?"
                display = (
                    f"**Multiple Products Matched:**\n"
                    f"- 1. {p1_name}\n"
                    f"- 2. {p2_name}\n\n"
                    f"Please specify which brand you would like to inspect."
                )
                return AssistantResponse(
                    intent="CLARIFICATION",
                    speech_text=speech,
                    display_text=display,
                    suggestions=[f"Check stock for {p1_name}", f"Check stock for {p2_name}"]
                )

        product = matched[0]
        today = date.today()
        usable_stock = await InventoryService.get_usable_stock(db, product.id, today)
        total_stock = await InventoryService.get_total_stock(db, product.id)

        status_label = "In stock"
        if usable_stock <= 0:
            status_label = "Out of stock"
        elif usable_stock <= product.reorder_threshold:
            status_label = "Low stock"

        qty_formatted = int(usable_stock) if usable_stock % 1 == 0 else float(usable_stock)
        unit_str = product.unit if qty_formatted == 1 else f"{product.unit}s"

        speech = (
            f"The current usable stock of {product.name} is {qty_formatted} {unit_str}."
        )
        display = (
            f"**Product:** {product.name} (SKU: `{product.sku}`)\n"
            f"**Available Usable Stock:** {qty_formatted} {unit_str}\n"
            f"**Total Stock (including expired lots):** {total_stock} {unit_str}\n"
            f"**Stock Status:** {status_label}\n"
            f"**Reorder Threshold:** {product.reorder_threshold} {unit_str}"
        )

        stock_info = StockInfo(
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            unit=product.unit,
            usable_stock=usable_stock,
            total_stock=total_stock,
            reorder_threshold=product.reorder_threshold,
            status=status_label,
        )

        first_word = product.name.split()[0]
        return AssistantResponse(
            intent="CHECK_STOCK",
            speech_text=speech,
            display_text=display,
            data=stock_info.model_dump(),
            suggestions=[
                f"Record a sale of 2 {product.unit}s of {first_word}",
                f"Which batch of {first_word} expires first?",
                "Which products are running low?",
            ],
        )

    @classmethod
    async def _handle_low_stock(
        cls, db: AsyncSession, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        today = date.today()
        res = await db.execute(select(Product).where(Product.is_active == True))
        products = res.scalars().all()

        low_items = []
        for p in products:
            usable = await InventoryService.get_usable_stock(db, p.id, today)
            if 0 < usable <= p.reorder_threshold:
                low_items.append({
                    "product_id": p.id,
                    "product_name": p.name,
                    "sku": p.sku,
                    "usable_stock": float(usable),
                    "reorder_threshold": float(p.reorder_threshold),
                    "unit": p.unit,
                })

        if not low_items:
            return AssistantResponse(
                intent="CHECK_LOW_STOCK",
                speech_text="Good news! There are currently no products running low on stock.",
                display_text="All active grocery products have healthy stock above their reorder thresholds.",
                data=[],
            )

        speech = f"There are {len(low_items)} products running low on stock, including {low_items[0]['product_name']}."
        display = f"**{len(low_items)} Products Running Low on Stock:**\n" + "\n".join([
            f"- **{item['product_name']}**: {item['usable_stock']} {item['unit']} remaining (Threshold: {item['reorder_threshold']})"
            for item in low_items
        ])

        return AssistantResponse(
            intent="CHECK_LOW_STOCK",
            speech_text=speech,
            display_text=display,
            data=low_items,
            suggestions=["What should I reorder today?", "Show all products currently out of stock"],
        )

    @classmethod
    async def _handle_out_of_stock(
        cls, db: AsyncSession, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        today = date.today()
        res = await db.execute(select(Product).where(Product.is_active == True))
        products = res.scalars().all()

        out_items = []
        for p in products:
            usable = await InventoryService.get_usable_stock(db, p.id, today)
            if usable <= 0:
                out_items.append({
                    "product_id": p.id,
                    "product_name": p.name,
                    "sku": p.sku,
                    "usable_stock": 0,
                    "unit": p.unit,
                })

        if not out_items:
            return AssistantResponse(
                intent="CHECK_OUT_OF_STOCK",
                speech_text="All active products currently have stock available. Zero products are out of stock.",
                display_text="No active products are out of stock.",
                data=[],
            )

        speech = f"{len(out_items)} products are currently completely out of stock, including {out_items[0]['product_name']}."
        display = f"**{len(out_items)} Products Out of Stock:**\n" + "\n".join([
            f"- **{item['product_name']}** (SKU: `{item['sku']}`)"
            for item in out_items
        ])

        return AssistantResponse(
            intent="CHECK_OUT_OF_STOCK",
            speech_text=speech,
            display_text=display,
            data=out_items,
            suggestions=["What should I reorder today?", "Which products are running low?"],
        )

    @classmethod
    async def _handle_expiry_queries(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        today = date.today()
        time_frame = (parsed.time_frame or "").lower()

        # Check for earliest batch of a specific product
        if "first" in text.lower() or "earliest" in text.lower() or parsed.product_raw:
            search_terms = [parsed.product_normalized, parsed.product_raw]
            matched = await cls.match_products(db, [t for t in search_terms if t])
            if matched:
                product = matched[0]
                result = await db.execute(
                    select(InventoryBatch)
                    .where(
                        InventoryBatch.product_id == product.id,
                        InventoryBatch.remaining_quantity > 0,
                        InventoryBatch.expiry_date.isnot(None),
                    )
                    .order_by(InventoryBatch.expiry_date.asc())
                    .limit(1)
                )
                earliest_batch = result.scalar_one_or_none()
                if earliest_batch:
                    days_left = (earliest_batch.expiry_date - today).days
                    days_str = (
                        "today" if days_left == 0 else f"in {days_left} days" if days_left > 0 else f"{abs(days_left)} days ago"
                    )
                    speech = (
                        f"The earliest expiring batch of {product.name} is Batch {earliest_batch.batch_number}, "
                        f"expiring {days_str} on {earliest_batch.expiry_date}. It has {earliest_batch.remaining_quantity} {product.unit}s remaining."
                    )
                    display = (
                        f"**Earliest Batch for {product.name} (FEFO Priority #1):**\n"
                        f"- Batch Number: `{earliest_batch.batch_number}`\n"
                        f"- Expiry Date: **{earliest_batch.expiry_date}** ({days_str})\n"
                        f"- Remaining Quantity: **{earliest_batch.remaining_quantity} {product.unit}**\n"
                    )
                    return AssistantResponse(
                        intent="CHECK_EXPIRY",
                        speech_text=speech,
                        display_text=display,
                        data={
                            "batch_number": earliest_batch.batch_number,
                            "product_name": product.name,
                            "remaining_quantity": float(earliest_batch.remaining_quantity),
                            "expiry_date": str(earliest_batch.expiry_date),
                            "days_left": days_left,
                        },
                    )

        # Expired items
        if time_frame == "expired" or "expired" in text.lower():
            result = await db.execute(
                select(InventoryBatch, Product)
                .join(Product, InventoryBatch.product_id == Product.id)
                .where(
                    InventoryBatch.remaining_quantity > 0,
                    InventoryBatch.expiry_date <= today,
                )
                .order_by(InventoryBatch.expiry_date.desc())
            )
            rows = result.all()
            if not rows:
                return AssistantResponse(
                    intent="CHECK_EXPIRY",
                    speech_text="Great news! There are zero expired products in stock.",
                    display_text="No batches have expired. All stored inventory is within shelf life.",
                    data=[],
                )

            speech = f"There are {len(rows)} expired batches in stock. The oldest is {rows[0][1].name}."
            display = f"**{len(rows)} Expired Batches in Stock:**\n" + "\n".join([
                f"- **{p.name}** (Batch `{b.batch_number}`): {b.remaining_quantity} {p.unit} expired on {b.expiry_date}"
                for b, p in rows
            ])
            return AssistantResponse(intent="CHECK_EXPIRY", speech_text=speech, display_text=display)

        # Expiring tomorrow
        if time_frame == "tomorrow" or "tomorrow" in text.lower() or "naalaiku" in text.lower():
            target_date = today + timedelta(days=1)
            result = await db.execute(
                select(InventoryBatch, Product)
                .join(Product, InventoryBatch.product_id == Product.id)
                .where(
                    InventoryBatch.remaining_quantity > 0,
                    InventoryBatch.expiry_date == target_date,
                )
                .order_by(InventoryBatch.expiry_date.asc())
            )
            rows = result.all()
            if not rows:
                return AssistantResponse(
                    intent="CHECK_EXPIRY",
                    speech_text="No products are scheduled to expire tomorrow.",
                    display_text=f"Zero batches expiring tomorrow ({target_date}).",
                    data=[],
                )

            speech = f"There are {len(rows)} batches expiring tomorrow: {', '.join([p.name for _, p in rows])}."
            display = f"**Batches Expiring Tomorrow ({target_date}):**\n" + "\n".join([
                f"- **{p.name}** (Batch `{b.batch_number}`): {b.remaining_quantity} {p.unit}"
                for b, p in rows
            ])
            return AssistantResponse(intent="CHECK_EXPIRY", speech_text=speech, display_text=display)

        # Default: Next 7 days
        end_date = today + timedelta(days=7)
        result = await db.execute(
            select(InventoryBatch, Product)
            .join(Product, InventoryBatch.product_id == Product.id)
            .where(
                InventoryBatch.remaining_quantity > 0,
                InventoryBatch.expiry_date >= today,
                InventoryBatch.expiry_date <= end_date,
            )
            .order_by(InventoryBatch.expiry_date.asc())
        )
        rows = result.all()
        if not rows:
            return AssistantResponse(
                intent="CHECK_EXPIRY",
                speech_text="No products are scheduled to expire in the next seven days.",
                display_text=f"No batches expiring between {today} and {end_date}.",
                data=[],
            )

        speech = f"There are {len(rows)} batches expiring in the next seven days, including {rows[0][1].name}."
        display = f"**Batches Expiring in the Next 7 Days (FEFO Priority):**\n" + "\n".join([
            f"- **{p.name}** (Batch `{b.batch_number}`): {b.remaining_quantity} {p.unit} expires on {b.expiry_date}"
            for b, p in rows
        ])
        return AssistantResponse(
            intent="CHECK_EXPIRY",
            speech_text=speech,
            display_text=display,
            data=[{
                "batch_number": b.batch_number,
                "product_name": p.name,
                "quantity": float(b.remaining_quantity),
                "unit": p.unit,
                "expiry_date": str(b.expiry_date),
                "days_left": (b.expiry_date - today).days,
            } for b, p in rows],
        )

    @classmethod
    async def _handle_sales_info(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        today = date.today()
        text_lower = text.lower()

        # Top selling product this week
        if "most" in text_lower or "top" in text_lower:
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            res = await db.execute(
                select(Product.name, func.sum(SaleItem.quantity).label("qty_sold"))
                .join(Product, SaleItem.product_id == Product.id)
                .join(Sale, SaleItem.sale_id == Sale.id)
                .where(Sale.sale_date >= week_ago, Sale.status == "COMPLETED")
                .group_by(Product.name)
                .order_by(desc("qty_sold"))
                .limit(1)
            )
            top = res.first()
            if top:
                speech = f"The top selling product this week is {top[0]} with {top[1]} units sold."
                display = f"**Top Selling Product This Week:**\n- **{top[0]}**: {top[1]} units sold"
            else:
                speech = "No sales recorded in the past week."
                display = "No completed sales in the past 7 days."
            return AssistantResponse(intent="SALES_INFO", speech_text=speech, display_text=display)

        # Today's sales summary
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        res = await db.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")),
                func.count(Sale.id),
            )
            .where(Sale.sale_date >= today_start, Sale.status == "COMPLETED")
        )
        total_amt, count = res.first() or (Decimal("0"), 0)
        amt_int = int(total_amt)

        speech = f"Today's sales total is {amt_int} rupees across {count} transactions."
        display = (
            f"### Today's Sales Performance\n"
            f"- **Total Revenue:** ₹{total_amt:,.2f}\n"
            f"- **Completed Transactions:** {count}\n"
            f"- **Date:** {today}"
        )
        return AssistantResponse(
            intent="SALES_INFO",
            speech_text=speech,
            display_text=display,
            data={"total_sales": float(total_amt), "total_transactions": count},
        )

    @classmethod
    async def _handle_reorder_recommendations(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        budget_val = None
        if parsed.budget:
            budget_val = Decimal(str(parsed.budget))
        else:
            budget_match = re.search(r"(\d+(?:,\d+)?)\s*(?:rooba|rupees|rs|budget)", text.lower())
            if budget_match:
                budget_val = Decimal(budget_match.group(1).replace(",", ""))

        if budget_val:
            try:
                plan = await BudgetOptimizer.create_budget_plan(db, budget_val)
                items = plan.items
                if items:
                    p_ids = [item.product_id for item in items]
                    p_res = await db.execute(select(Product).where(Product.id.in_(p_ids)))
                    prod_map = {p.id: p for p in p_res.scalars().all()}

                    speech = (
                        f"With a budget of {int(budget_val)} rupees, StockSense recommends purchasing "
                        f"{len(items)} products for an allocated total of {int(plan.total_allocated)} rupees."
                    )
                    display = (
                        f"### AI Budget-Constrained Purchasing Plan (Budget: ₹{budget_val:,.2f})\n"
                        + "\n".join([
                            f"- **{prod_map[item.product_id].name if item.product_id in prod_map else 'Product'}**: "
                            f"{item.suggested_quantity} units (~₹{item.line_cost:,.2f}) — {item.priority or 'HIGH'} priority"
                            for item in items
                        ])
                        + f"\n\n**Total Allocated:** ₹{plan.total_allocated:,.2f} | **Remaining Cash Buffer:** ₹{plan.remaining_budget:,.2f}"
                    )
                    return AssistantResponse(
                        intent="AI_RECOMMENDATION",
                        speech_text=speech,
                        display_text=display,
                        data=[{
                            "product_name": prod_map[item.product_id].name if item.product_id in prod_map else f"Product {item.product_id}",
                            "quantity": float(item.suggested_quantity),
                            "line_total": float(item.line_cost),
                            "unit_cost": float(item.unit_cost),
                        } for item in items],
                    )
            except Exception as e:
                logger.error(f"Budget optimizer error: {e}")

        # General Reorder recommendations
        recs = await ReorderEngine.calculate_recommendations(db)
        actionable = [r for r in recs if r.suggested_quantity and r.suggested_quantity > 0]

        if not actionable:
            return AssistantResponse(
                intent="AI_RECOMMENDATION",
                speech_text="Stock levels are healthy across all products. No reorders needed today.",
                display_text="All active products have adequate stock coverage. Zero stockouts predicted.",
                data=[],
            )

        p_ids = [r.product_id for r in actionable]
        p_res = await db.execute(select(Product).where(Product.id.in_(p_ids)))
        prod_map = {p.id: p for p in p_res.scalars().all()}

        top_recs = actionable[:4]
        items_summary = ", ".join([
            f"{int(r.suggested_quantity)} units of {prod_map[r.product_id].name if r.product_id in prod_map else 'item'}"
            for r in top_recs[:2]
        ])
        speech = f"StockSense recommends reordering {len(actionable)} products today, including {items_summary}."
        display = f"### AI Reorder Recommendations ({len(actionable)} items)\n" + "\n".join([
            f"- **{prod_map[r.product_id].name if r.product_id in prod_map else 'Item'}**: Reorder **{r.suggested_quantity} {prod_map[r.product_id].unit if r.product_id in prod_map else 'units'}** (Est. Cost: ₹{r.estimated_cost:,.2f})"
            for r in top_recs
        ])

        return AssistantResponse(
            intent="AI_RECOMMENDATION",
            speech_text=speech,
            display_text=display,
            data=[{
                "product_id": r.product_id,
                "product_name": prod_map[r.product_id].name if r.product_id in prod_map else f"Product {r.product_id}",
                "suggested_quantity": float(r.suggested_quantity),
                "unit": prod_map[r.product_id].unit if r.product_id in prod_map else "unit",
                "estimated_cost": float(r.estimated_cost),
                "explanation": r.explanation,
                "priority": r.priority,
            } for r in top_recs],
            suggestions=["Recommend purchases within my 2,000 rupee budget", "Which products are running low?"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # B. STOCK MUTATIONS: RECORD A SALE (TWO-PHASE CONFIRMATION GATE)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_record_sale(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent, session_id: str
    ) -> AssistantResponse:
        search_terms = [parsed.product_normalized, parsed.product_raw, text]
        matched = await cls.match_products(db, [t for t in search_terms if t])

        if not matched:
            return AssistantResponse(
                intent="RECORD_SALE",
                speech_text="I couldn't identify which product you want to sell. Please specify the product name.",
                display_text="Product not recognized in catalog. Example: 'Record a sale of 2 milk packets'",
                suggestions=["Record a sale of 2 milk packets", "5 packet biscuit sale panniten"],
            )

        product = matched[0]
        qty_num = parsed.quantity if parsed.quantity is not None else parse_number_from_text(text)
        qty = Decimal(str(qty_num)) if qty_num else Decimal("1")

        # Validate stock availability
        today = date.today()
        usable_stock = await InventoryService.get_usable_stock(db, product.id, today)
        if usable_stock < qty:
            speech = f"Cannot record sale. Only {usable_stock} {product.unit} of {product.name} are available in stock, but you requested {qty}."
            display = (
                f"⚠️ **Insufficient Usable Stock!**\n"
                f"- Product: **{product.name}**\n"
                f"- Available Usable Stock: **{usable_stock} {product.unit}**\n"
                f"- Requested: **{qty} {product.unit}**\n"
            )
            return AssistantResponse(
                intent="RECORD_SALE",
                speech_text=speech,
                display_text=display,
                error="INSUFFICIENT_STOCK",
            )

        line_total = qty * product.selling_price
        unit_str = product.unit if qty == 1 else f"{product.unit}s"

        speech_prompt = f"Record a sale of {int(qty) if qty % 1 == 0 else qty} {unit_str} of {product.name} for {int(line_total)} rupees?"
        display_prompt = (
            f"### Confirm Sale Transaction\n"
            f"- **Product:** {product.name}\n"
            f"- **Quantity:** {qty} {unit_str}\n"
            f"- **Unit Price:** ₹{product.selling_price}\n"
            f"- **Total Amount:** ₹{line_total:,.2f}\n"
            f"- **Remaining Usable Stock After Sale:** {usable_stock - qty} {unit_str}\n\n"
            f"*Do you want to confirm and complete this sale?*"
        )

        action_payload = {
            "action": "RECORD_SALE",
            "product_id": product.id,
            "product_name": product.name,
            "quantity": float(qty),
            "unit": product.unit,
            "unit_price": float(product.selling_price),
            "line_total": float(line_total),
        }

        # Store pending proposal in session store for multi-turn correction or confirmation
        SessionStore.set_pending_proposal(session_id, action_payload)

        return AssistantResponse(
            intent="RECORD_SALE",
            speech_text=speech_prompt,
            display_text=display_prompt,
            requires_confirmation=True,
            action_payload=action_payload,
            data=action_payload,
            suggestions=["Aama, confirm pannu", "Illa, 3 packet mattum", "Cancel pannidu"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # C. STOCK MUTATIONS: RECEIVE NEW STOCK (TWO-PHASE CONFIRMATION GATE)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_receive_stock(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent, session_id: str
    ) -> AssistantResponse:
        search_terms = [parsed.product_normalized, parsed.product_raw, text]
        matched = await cls.match_products(db, [t for t in search_terms if t])

        if not matched:
            return AssistantResponse(
                intent="RECEIVE_STOCK",
                speech_text="I couldn't identify which product to receive stock for. Please specify the product name.",
                display_text="Product not found in catalog. Example: '10 kilo tomato vandhiruchu, stock update pannu'",
                suggestions=["We received 20 biscuit packets", "10 kilo tomato vandhiruchu, stock update pannu"],
            )

        product = matched[0]
        qty_num = parsed.quantity if parsed.quantity is not None else parse_number_from_text(text)
        qty = Decimal(str(qty_num)) if qty_num else Decimal("10")

        # Expiry date handling
        expiry = None
        if product.shelf_life_days:
            expiry = date.today() + timedelta(days=product.shelf_life_days)

        unit_str = product.unit if qty == 1 else f"{product.unit}s"
        batch_number = f"BAT-{datetime.now().strftime('%y%m%d%H%M')}"

        speech_prompt = f"Add {int(qty) if qty % 1 == 0 else qty} {unit_str} of {product.name} to stock?"
        display_prompt = (
            f"### Confirm Inbound Stock Receipt\n"
            f"- **Product:** {product.name}\n"
            f"- **Quantity to Add:** +{qty} {unit_str}\n"
            f"- **Unit Cost:** ₹{product.purchase_cost}\n"
            f"- **Generated Batch Number:** `{batch_number}`\n"
            f"- **Calculated Expiry Date:** {expiry or 'Non-perishable'}\n\n"
            f"*Do you want to confirm and receive this stock into inventory?*"
        )

        action_payload = {
            "action": "RECEIVE_STOCK",
            "product_id": product.id,
            "product_name": product.name,
            "quantity": float(qty),
            "unit": product.unit,
            "unit_cost": float(product.purchase_cost),
            "batch_number": batch_number,
            "expiry_date": str(expiry) if expiry else None,
        }

        # Store pending proposal in session store
        SessionStore.set_pending_proposal(session_id, action_payload)

        return AssistantResponse(
            intent="RECEIVE_STOCK",
            speech_text=speech_prompt,
            display_text=display_prompt,
            requires_confirmation=True,
            action_payload=action_payload,
            data=action_payload,
            suggestions=["Aama, confirm pannu", "Illa, 5 kg mattum", "Cancel pannidu"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # D. CONFIRMED ACTIONS EXECUTOR (STRICT TRANSACTIONAL BOUNDARY)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _execute_confirmed_action(
        cls, db: AsyncSession, payload: Dict[str, Any]
    ) -> AssistantResponse:
        action = payload.get("action")

        if action == "RECORD_SALE":
            product_id = payload["product_id"]
            qty = Decimal(str(payload["quantity"]))
            unit_price = Decimal(str(payload["unit_price"]))

            item = SaleItemCreate(
                product_id=product_id,
                quantity=qty,
                unit_price=unit_price,
            )
            try:
                sale = await SalesService.create_sale(
                    db=db,
                    items=[item],
                    notes="Recorded via StockSense Voice Assistant",
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to record sale: {e}")
                return AssistantResponse(
                    intent="RECORD_SALE",
                    speech_text=f"Failed to record sale: {str(e)}",
                    display_text=f"Transaction error: {str(e)}",
                    error=str(e),
                )

            speech = f"Sale recorded successfully for {payload['quantity']} {payload['unit']} of {payload['product_name']}. Receipt number is {sale.sale_number}."
            display = (
                f"### Sale Completed Successfully\n"
                f"- **Sale Number:** `{sale.sale_number}`\n"
                f"- **Product:** {payload['product_name']}\n"
                f"- **Quantity Deducted:** -{payload['quantity']} {payload['unit']} (FEFO order)\n"
                f"- **Total Amount:** ₹{payload['line_total']:,.2f}\n"
                f"- **Status:** COMPLETED & COMMITTED TO LEDGER"
            )
            return AssistantResponse(
                intent="RECORD_SALE",
                speech_text=speech,
                display_text=display,
                data={"sale_number": sale.sale_number, "total_amount": payload["line_total"]},
            )

        elif action == "RECEIVE_STOCK":
            product_id = payload["product_id"]
            qty = Decimal(str(payload["quantity"]))
            unit_cost = Decimal(str(payload["unit_cost"]))
            batch_num = payload.get("batch_number")
            expiry_str = payload.get("expiry_date")
            expiry_date = date.fromisoformat(expiry_str) if expiry_str else None

            try:
                batch, movement = await InventoryService.create_stock_receipt(
                    db=db,
                    product_id=product_id,
                    quantity=qty,
                    unit_cost=unit_cost,
                    batch_number=batch_num,
                    expiry_date=expiry_date,
                    source_type="DIRECT",
                    notes="Received via StockSense Voice Assistant",
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to receive stock: {e}")
                return AssistantResponse(
                    intent="RECEIVE_STOCK",
                    speech_text=f"Failed to receive stock: {str(e)}",
                    display_text=f"Stock receipt error: {str(e)}",
                    error=str(e),
                )

            speech = f"Stock received! Added {payload['quantity']} {payload['unit']} of {payload['product_name']} under batch {batch.batch_number}."
            display = (
                f"### Stock Received & Ledger Updated\n"
                f"- **Product:** {payload['product_name']}\n"
                f"- **Quantity Added:** +{payload['quantity']} {payload['unit']}\n"
                f"- **Batch Lot:** `{batch.batch_number}`\n"
                f"- **Expiry Date:** {expiry_date or 'Non-perishable'}\n"
                f"- **Status:** COMMITTED TO INVENTORY"
            )
            return AssistantResponse(
                intent="RECEIVE_STOCK",
                speech_text=speech,
                display_text=display,
                data={"batch_number": batch.batch_number, "quantity_added": float(qty)},
            )

        return AssistantResponse(
            intent="UNKNOWN",
            speech_text="Unknown action payload.",
            display_text="Unknown confirmed action.",
        )
