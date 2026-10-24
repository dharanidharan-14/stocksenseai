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

# Stop words to exclude from product search candidate tokenization
STOP_WORDS: set[str] = {
    "the", "a", "an", "on", "in", "at", "to", "for", "of", "with", "is", "are",
    "this", "that", "these", "those", "product", "item", "items", "stock",
    "remove", "add", "delete", "offer", "discount", "percent", "percentage",
    "how", "much", "many", "what", "which", "show", "check", "tell", "evlo",
    "irukku", "enna", "la", "ku", "oru", "mattum", "bro", "bhai", "please",
    "packet", "packets", "kg", "kgs", "bag", "bags", "bottle", "bottles",
    "box", "boxes", "piece", "pieces", "gram", "grams", "g", "litre", "litres", "l",
    "can", "you", "me", "i", "we", "he", "she", "it", "they", "my", "our", "your",
    "here", "there", "give", "take", "bring", "send", "got", "get", "need", "want"
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
        raw terms, and regional aliases, strictly filtering out common stop words.
        """
        result = await db.execute(select(Product).where(Product.is_active == True))
        all_products = result.scalars().all()

        tokens = set()
        for term in search_terms:
            if not term:
                continue
            t_clean = term.lower().strip()
            # Direct alias match
            if t_clean in REGIONAL_ALIASES:
                tokens.add(REGIONAL_ALIASES[t_clean])
            for word in re.findall(r"\b[a-zA-Z0-9]+\b", t_clean):
                if word in STOP_WORDS:
                    continue
                if len(word) >= 3 or word in REGIONAL_ALIASES:
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
                # Exact whole word match gets highest score
                if re.search(r"\b" + re.escape(token) + r"\b", p_name_lower):
                    score += 10
                elif len(token) >= 4 and token in p_name_lower:
                    score += 3
                if token in p_sku_lower:
                    score += 5
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
        language_preference: Optional[str] = "tanglish",
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
                spoken_reply_tamil="Transaction cancel aaidichu.",
                spoken_reply_english="Transaction cancelled.",
                spoken_reply_tanglish="Transaction cancel aaidichu.",
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
                    spoken_reply_tamil="Confirm panna endha transaction-um illai. Enna seiya vendum?",
                    spoken_reply_english="There is no pending transaction to confirm. What would you like to do?",
                    spoken_reply_tanglish="Confirm panna pending transaction edhuvum illa.",
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
                    spoken_reply_tamil=f"{pending['quantity']} {pending['unit']} {pending['product_name']}-a maathittaen. Confirm pannunga.",
                    spoken_reply_english=speech,
                    spoken_reply_tanglish=f"{pending['quantity']} {pending['unit']} {pending['product_name']}-a update pannittaen. Confirm pannalaamaa?",
                    suggestions=["Aama, confirm pannu", "Cancel pannidu"]
                )
                SessionStore.append_turn(session_id, "assistant", resp.speech_text)
                return resp

        # ─── 6. ROUTE BASED ON CAPABILITY BOUNDARIES & INTENT ───
        intent = parsed.intent

        if intent == "DISCOUNT_OR_OFFER":
            resp = await cls._handle_discount_or_offer(db, text, parsed)
        elif intent == "PRICE_MODIFICATION":
            resp = await cls._handle_price_modification(db, text, parsed)
        elif intent == "UNSUPPORTED":
            resp = await cls._handle_unsupported(db, text, parsed)
        elif intent == "CLARIFICATION":
            resp = AssistantResponse(
                intent="CLARIFICATION",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text=parsed.clarification_question or parsed.spoken_reply_english or "Could you please clarify that command?",
                display_text=parsed.clarification_question or "Please provide additional details to complete this request.",
                raw_transcript=text,
                spoken_reply_tamil="Dhayavuseidhu vilakkamaaga kooravum.",
                spoken_reply_english=parsed.clarification_question or "Could you please clarify that command?",
                spoken_reply_tanglish="Konjam clarify pannunga bro.",
                suggestions=["How much rice stock is left?", "Record a sale of 2 milk packets"],
            )
        elif intent == "CHECK_STOCK":
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
        elif intent == "ADD_TO_CART":
            resp = await cls._handle_add_to_cart(db, text, parsed)
        elif intent == "REMOVE_FROM_CART":
            resp = await cls._handle_remove_from_cart(db, text, parsed)
        elif intent == "CHECK_BILL_TOTAL":
            resp = await cls._handle_check_bill_total(db, text, parsed)
        elif intent == "CLEAR_BILL":
            resp = await cls._handle_clear_bill(db, text, parsed)
        else:
            # Explicitly reject unknown commands without falling back to a stock check
            resp = AssistantResponse(
                intent="UNKNOWN",
                confidence_status="UNSUPPORTED",
                speech_text=parsed.spoken_reply_tamil or parsed.spoken_reply_english or "I did not understand that command. You can ask about stock, sales, or record transactions.",
                display_text=(
                    "I couldn't identify a supported grocery inventory command in that request.\n"
                    "StockSense AI supports stock lookups, sales, receipts, expiry alerts, and purchase recommendations."
                ),
                raw_transcript=text,
                spoken_reply_tamil="Enakku puriyavillai. Stock, sales, alladhu transactions patri ketkalaam.",
                spoken_reply_english="I did not understand that command. You can ask about stock, sales, or record transactions.",
                spoken_reply_tanglish="Puriyala bro. Stock, sales, alladhu cart billing patri kekkalaam.",
                suggestions=[
                    "Tomato stock la evlo irukku?",
                    "Innaiku sales evlo?",
                    "Naalaiku expire aagura items enna?",
                    "What should I reorder today?",
                    "Record a sale of 2 milk packets",
                ],
            )

        resp.raw_transcript = text

        # Select speech text based on user language preference
        lang_pref = (language_preference or "tanglish").lower()
        if lang_pref == "tamil" and getattr(resp, "spoken_reply_tamil", None):
            resp.speech_text = resp.spoken_reply_tamil
        elif lang_pref == "english" and getattr(resp, "spoken_reply_english", None):
            resp.speech_text = resp.spoken_reply_english
        elif lang_pref in ["tanglish", "thanglish"] and getattr(resp, "spoken_reply_tanglish", None):
            resp.speech_text = resp.spoken_reply_tanglish

        SessionStore.append_turn(session_id, "assistant", resp.speech_text)
        return resp

    # ──────────────────────────────────────────────────────────────────────────
    # CAPABILITY BOUNDARY HANDLERS (DISCOUNTS, PRICING, UNSUPPORTED)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_discount_or_offer(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        """
        Handles requests to add, remove, or modify discounts/offers.
        Inspects application schema and honestly communicates that discount management
        is not supported in this application, ensuring zero mutations to stock or pricing.
        """
        product_note = ""
        candidates = [t for t in [parsed.product_normalized, parsed.product_raw] if t]
        matched = await cls.match_products(db, candidates) if candidates else []

        if "this product" in text.lower():
            product_note = "\n- **Note:** The product reference ('this product') is ambiguous and was not specified."
        elif matched:
            product_note = f"\n- **Referenced Product:** {matched[0].name}"

        discount_str = f" ({int(parsed.discount_percent)}%)" if parsed.discount_percent else ""

        speech = (
            f"Discount and offer management{discount_str} is not currently supported in StockSense AI. "
            f"No changes were made to prices or inventory."
        )
        display = (
            f"⚠️ **Unsupported Operation: Discount & Offer Management**\n\n"
            f"You requested: *\"{text}\"*\n"
            f"{product_note}\n\n"
            f"**System Capability Status:**\n"
            f"- Discount, coupon, and promotional offer management is **not supported** in the current database schema.\n"
            f"- StockSense AI is strictly configured for batch inventory tracking, FEFO deductions, sales, and demand forecasting.\n\n"
            f"🛡️ **Integrity Guarantee:** Zero changes have been made to product prices, discounts, or inventory ledgers."
        )

        return AssistantResponse(
            intent="DISCOUNT_OR_OFFER",
            confidence_status="UNSUPPORTED",
            speech_text=speech,
            display_text=display,
            raw_transcript=text,
            requires_confirmation=False,
            suggestions=[
                "How much rice stock is left?",
                "Innaiku sales evlo?",
                "What should I reorder today?",
            ],
        )

    @classmethod
    async def _handle_price_modification(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        """
        Handles requests to change selling price or purchase cost.
        Refuses voice-driven price mutation and redirects to product catalog.
        """
        speech = "Price modification via voice assistant is not supported. Please edit prices in the product catalog."
        display = (
            f"⚠️ **Unsupported Operation: Price Modification**\n\n"
            f"You requested: *\"{text}\"*\n\n"
            f"**System Capability Status:**\n"
            f"- Selling prices and purchase costs cannot be modified via voice assistant.\n"
            f"- To adjust prices, please use the Product Management screen.\n\n"
            f"🛡️ **Integrity Guarantee:** No changes were made to product prices or stock."
        )
        return AssistantResponse(
            intent="PRICE_MODIFICATION",
            confidence_status="UNSUPPORTED",
            speech_text=speech,
            display_text=display,
            raw_transcript=text,
            requires_confirmation=False,
            suggestions=["How much rice stock is left?", "Innaiku sales evlo?"],
        )

    @classmethod
    async def _handle_unsupported(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        """
        Handles any other operation outside the supported Kirana inventory features.
        """
        reason = parsed.unsupported_reason or "This operation is not supported by the StockSense AI inventory system."
        speech = f"{reason} No changes were made."
        display = (
            f"⚠️ **Unsupported Capability**\n\n"
            f"You requested: *\"{text}\"*\n\n"
            f"{reason}\n\n"
            f"Supported features: stock availability, low stock alerts, expiring batches, sales summary, "
            f"reorder recommendations, recording sales, and stock receipts."
        )
        return AssistantResponse(
            intent="UNSUPPORTED",
            confidence_status="UNSUPPORTED",
            speech_text=speech,
            display_text=display,
            raw_transcript=text,
            requires_confirmation=False,
            suggestions=["How much rice stock is left?", "Innaiku sales evlo?", "What should I reorder today?"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # A. READ-ONLY INVENTORY QUERIES
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_check_stock(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        search_candidates = [t for t in [parsed.product_normalized, parsed.product_raw] if t]
        matched = await cls.match_products(db, search_candidates if search_candidates else [text])

        if not matched:
            spoken = parsed.spoken_reply_tamil or parsed.spoken_reply_english or "No matching product found in inventory."
            return AssistantResponse(
                intent="CHECK_STOCK",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text=spoken,
                display_text=f"No active product in your catalog matches '{parsed.product_raw or parsed.product_normalized or text}'. Please check spelling or product name.",
                raw_transcript=text,
                suggestions=["Show all products currently out of stock", "Which products are running low?"]
            )

        # Ambiguity guard: If multiple distinct products match and user query was generic (e.g. "milk")
        if len(matched) > 1:
            user_kw = (parsed.product_raw or parsed.product_normalized or "").lower().strip()
            if not any(user_kw == p.name.lower() or user_kw == p.sku.lower() for p in matched[:3]):
                top_items = matched[:3]
                speech = f"Multiple products match '{user_kw or 'your request'}': {top_items[0].name} or {top_items[1].name}. Which one would you like to check?"
                display = (
                    f"**Multiple Products Matched:**\n"
                    + "\n".join([f"- **{p.name}** (SKU: `{p.sku}`)" for p in top_items])
                    + "\n\nPlease specify which brand or variant you would like to inspect."
                )
                return AssistantResponse(
                    intent="CLARIFICATION",
                    confidence_status="AMBIGUOUS",
                    speech_text=speech,
                    display_text=display,
                    raw_transcript=text,
                    suggestions=[f"Check stock for {p.name}" for p in top_items],
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
        # Resolve product from extracted candidates first
        candidates = [t for t in [parsed.product_normalized, parsed.product_raw] if t]
        matched = await cls.match_products(db, candidates if candidates else [text])

        if not matched:
            return AssistantResponse(
                intent="CLARIFICATION",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text="I couldn't identify which product you want to sell. Please specify the product name.",
                display_text="Product not recognized in your catalog. Please state the product name (e.g. 'Record a sale of 2 milk packets').",
                raw_transcript=text,
                suggestions=["Record a sale of 2 milk packets", "5 packet biscuit sale panniten"],
            )

        # Ambiguity guard: check if generic term matched multiple products
        if len(matched) > 1:
            user_kw = (parsed.product_raw or parsed.product_normalized or "").lower().strip()
            # If user did not provide an exact name match
            if not any(user_kw == p.name.lower() or user_kw == p.sku.lower() for p in matched[:3]):
                top_items = matched[:3]
                speech = f"Multiple products match '{user_kw or 'your request'}': {top_items[0].name} or {top_items[1].name}. Which one would you like to sell?"
                display = (
                    f"**Multiple Product Candidates Found:**\n"
                    + "\n".join([f"- **{p.name}** (SKU: `{p.sku}`, Price: ₹{p.selling_price})" for p in top_items])
                    + "\n\nPlease clarify which exact product you would like to sell."
                )
                return AssistantResponse(
                    intent="CLARIFICATION",
                    confidence_status="AMBIGUOUS",
                    speech_text=speech,
                    display_text=display,
                    raw_transcript=text,
                    suggestions=[f"Record a sale of {p.name.split()[0]}" for p in top_items],
                )

        product = matched[0]

        # Parameter validation: DO NOT GUESS MISSING QUANTITIES
        qty_num = parsed.quantity if parsed.quantity is not None else parse_number_from_text(text)
        if qty_num is None:
            speech = f"How many {product.unit}s of {product.name} would you like to sell?"
            display = f"Please specify the quantity to sell for **{product.name}**."
            return AssistantResponse(
                intent="CLARIFICATION",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text=speech,
                display_text=display,
                raw_transcript=text,
                suggestions=[
                    f"Record a sale of 1 {product.unit} of {product.name.split()[0]}",
                    f"Record a sale of 2 {product.unit}s of {product.name.split()[0]}",
                ],
            )

        qty = Decimal(str(qty_num))
        if qty <= 0:
            return AssistantResponse(
                intent="RECORD_SALE",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text="Quantity must be greater than zero.",
                display_text="Sale quantity must be a positive number.",
                raw_transcript=text,
            )

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
                confidence_status="CONFIRMED",
                speech_text=speech,
                display_text=display,
                error="INSUFFICIENT_STOCK",
                raw_transcript=text,
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
            confidence_status="CONFIRMED",
            speech_text=speech_prompt,
            display_text=display_prompt,
            requires_confirmation=True,
            action_payload=action_payload,
            data=action_payload,
            raw_transcript=text,
            suggestions=["Aama, confirm pannu", "Illa, 3 packet mattum", "Cancel pannidu"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # C. STOCK MUTATIONS: RECEIVE NEW STOCK (TWO-PHASE CONFIRMATION GATE)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_receive_stock(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent, session_id: str
    ) -> AssistantResponse:
        # Resolve product from candidates first
        candidates = [t for t in [parsed.product_normalized, parsed.product_raw] if t]
        matched = await cls.match_products(db, candidates if candidates else [text])

        if not matched:
            return AssistantResponse(
                intent="CLARIFICATION",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text="I couldn't identify which product to receive stock for. Please specify the product name.",
                display_text="Product not found in catalog. Example: '10 kilo tomato vandhiruchu, stock update pannu'",
                raw_transcript=text,
                suggestions=["We received 20 biscuit packets", "10 kilo tomato vandhiruchu, stock update pannu"],
            )

        # Ambiguity guard
        if len(matched) > 1:
            user_kw = (parsed.product_raw or parsed.product_normalized or "").lower().strip()
            if not any(user_kw == p.name.lower() or user_kw == p.sku.lower() for p in matched[:3]):
                top_items = matched[:3]
                speech = f"Multiple products match '{user_kw or 'your request'}': {top_items[0].name} or {top_items[1].name}. Which one did you receive?"
                display = (
                    f"**Multiple Product Candidates Found:**\n"
                    + "\n".join([f"- **{p.name}** (SKU: `{p.sku}`)" for p in top_items])
                    + "\n\nPlease clarify which exact product was received."
                )
                return AssistantResponse(
                    intent="CLARIFICATION",
                    confidence_status="AMBIGUOUS",
                    speech_text=speech,
                    display_text=display,
                    raw_transcript=text,
                    suggestions=[f"Received 10 {p.unit}s of {p.name.split()[0]}" for p in top_items],
                )

        product = matched[0]

        # Parameter validation: DO NOT GUESS MISSING QUANTITIES
        qty_num = parsed.quantity if parsed.quantity is not None else parse_number_from_text(text)
        if qty_num is None:
            speech = f"How many {product.unit}s of {product.name} did you receive?"
            display = f"Please specify the quantity received for **{product.name}**."
            return AssistantResponse(
                intent="CLARIFICATION",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text=speech,
                display_text=display,
                raw_transcript=text,
                suggestions=[
                    f"Received 10 {product.unit}s of {product.name.split()[0]}",
                    f"Received 20 {product.unit}s of {product.name.split()[0]}",
                ],
            )

        qty = Decimal(str(qty_num))
        if qty <= 0:
            return AssistantResponse(
                intent="RECEIVE_STOCK",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text="Received quantity must be greater than zero.",
                display_text="Received quantity must be a positive number.",
                raw_transcript=text,
            )

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
            confidence_status="CONFIRMED",
            speech_text=speech_prompt,
            display_text=display_prompt,
            requires_confirmation=True,
            action_payload=action_payload,
            data=action_payload,
            raw_transcript=text,
            suggestions=["Aama, confirm pannu", "Illa, 5 kg mattum", "Cancel pannidu"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # D. BILLING & POS CART ACTIONS (VOICE-CONTROLLED BASKET MANIPULATION)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_add_to_cart(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        candidates = [t for t in [parsed.product_normalized, parsed.product_raw] if t]
        matched = await cls.match_products(db, candidates if candidates else [text])

        if not matched:
            return AssistantResponse(
                intent="CLARIFICATION",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text="I couldn't identify which product you want to add to the bill. Please specify the product name.",
                display_text="Product not recognized in catalog. Please specify the product name (e.g., 'Add 2 Nandini milk to cart').",
                raw_transcript=text,
                spoken_reply_tamil="Endha product bill la add pannanum? Product peyar sollunga.",
                spoken_reply_english="Which product would you like to add to the bill? Please state the name.",
                spoken_reply_tanglish="Endha product bill-la add pannanum? Product name sollunga.",
                suggestions=["Add 2 Nandini milk to cart", "Add 1 kg sugar to bill"],
            )

        if len(matched) > 1:
            user_kw = (parsed.product_raw or parsed.product_normalized or "").lower().strip()
            if not any(user_kw == p.name.lower() or user_kw == p.sku.lower() for p in matched[:3]):
                top_items = matched[:3]
                speech = f"Multiple products match: {top_items[0].name} or {top_items[1].name}. Which one would you like to add to the bill?"
                display = (
                    f"**Multiple Product Candidates Found:**\n"
                    + "\n".join([f"- **{p.name}** (SKU: `{p.sku}`, Price: ₹{p.selling_price})" for p in top_items])
                    + "\n\nPlease clarify which exact product you would like to add."
                )
                return AssistantResponse(
                    intent="CLARIFICATION",
                    confidence_status="AMBIGUOUS",
                    speech_text=speech,
                    display_text=display,
                    raw_transcript=text,
                    spoken_reply_tamil=f"{top_items[0].name} alladhu {top_items[1].name} - endha product bill la add pannanum?",
                    spoken_reply_english=speech,
                    spoken_reply_tanglish=f"{top_items[0].name} or {top_items[1].name} - edha cart la add pannanum?",
                    suggestions=[f"Add {p.name.split()[0]} to bill" for p in top_items],
                )

        product = matched[0]
        usable_stock = await InventoryService.get_usable_stock(db, product.id)
        if usable_stock <= 0:
            speech = f"{product.name} is currently out of stock. Cannot add to bill."
            return AssistantResponse(
                intent="ADD_TO_CART",
                confidence_status="CONFIRMED",
                speech_text=speech,
                display_text=f"⚠️ **Out of Stock:** **{product.name}** has 0 units in stock. Cannot add to bill.",
                raw_transcript=text,
                spoken_reply_tamil=f"{product.name} tharpodhu stock la illai. Bill la add panna mudiyaadhu.",
                spoken_reply_english=speech,
                spoken_reply_tanglish=f"{product.name} out of stock. Bill la podamudiyadhu.",
            )

        qty_num = parsed.quantity if parsed.quantity is not None else parse_number_from_text(text)
        if qty_num is None:
            qty_num = Decimal("1")
        else:
            qty_num = Decimal(str(qty_num))

        if qty_num > usable_stock:
            speech = f"Only {usable_stock} {product.unit}s of {product.name} available in stock. Cannot add {qty_num}."
            return AssistantResponse(
                intent="ADD_TO_CART",
                confidence_status="CONFIRMED",
                speech_text=speech,
                display_text=f"⚠️ **Insufficient Stock:** Available: {usable_stock} {product.unit}s. Requested: {qty_num}.",
                raw_transcript=text,
                spoken_reply_tamil=f"{product.name} stock la {usable_stock} {product.unit} dhaan irukku. {qty_num} add panna mudiyaadhu.",
                spoken_reply_english=speech,
                spoken_reply_tanglish=f"{product.name} stock-la {usable_stock} {product.unit} mattum dhaan irukku.",
            )

        line_total = float(qty_num * product.selling_price)
        speech_en = f"Added {qty_num} {product.unit} of {product.name} to the bill at ₹{product.selling_price:.2f} each. Line total is ₹{line_total:.2f}."
        speech_ta = f"{qty_num} {product.unit} {product.name} bill-la sethutaen. Vilai ₹{line_total:.2f}."
        speech_tgl = f"{qty_num} {product.unit} {product.name} bill-la add pannittaen. Line total ₹{line_total:.2f}."

        display = (
            f"🛒 **Added to Bill (POS Basket):**\n"
            f"- **Product:** {product.name}\n"
            f"- **Quantity:** {qty_num} {product.unit}\n"
            f"- **Unit Price:** ₹{product.selling_price:,.2f}\n"
            f"- **Line Total:** ₹{line_total:,.2f}\n"
            f"- **Batch Allocation:** FEFO auto-allocated on checkout"
        )

        return AssistantResponse(
            intent="ADD_TO_CART",
            confidence_status="CONFIRMED",
            speech_text=speech_en,
            display_text=display,
            spoken_reply_english=speech_en,
            spoken_reply_tamil=speech_ta,
            spoken_reply_tanglish=speech_tgl,
            raw_transcript=text,
            action_payload={
                "action": "ADD_TO_CART",
                "product_id": product.id,
                "product_name": product.name,
                "quantity": float(qty_num),
                "unit_price": float(product.selling_price),
                "unit": product.unit,
                "image_url": product.image_url,
                "line_total": line_total,
            },
            data={
                "product_id": product.id,
                "product_name": product.name,
                "quantity": float(qty_num),
                "unit_price": float(product.selling_price),
                "unit": product.unit,
                "image_url": product.image_url,
                "line_total": line_total,
            },
            suggestions=["What is the bill total?", "Add another item to bill", "Clear the bill"],
        )

    @classmethod
    async def _handle_remove_from_cart(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        candidates = [t for t in [parsed.product_normalized, parsed.product_raw] if t]
        matched = await cls.match_products(db, candidates if candidates else [text])

        if not matched:
            return AssistantResponse(
                intent="CLARIFICATION",
                confidence_status="NEEDS_CLARIFICATION",
                speech_text="Which product would you like to remove from the bill?",
                display_text="Please specify which product to remove from the bill.",
                raw_transcript=text,
                spoken_reply_tamil="Endha product-a bill la irundhu remove pannanum?",
                spoken_reply_english="Which product would you like to remove from the bill?",
                spoken_reply_tanglish="Endha item-a cart la irundhu remove pannanum?",
            )

        product = matched[0]
        speech_en = f"Removed {product.name} from the bill."
        speech_ta = f"{product.name}-a bill-la irundhu neekkittaen."
        speech_tgl = f"{product.name}-a bill-la irundhu remove pannittaen."

        return AssistantResponse(
            intent="REMOVE_FROM_CART",
            confidence_status="CONFIRMED",
            speech_text=speech_en,
            display_text=f"🗑️ **Removed from Bill:** **{product.name}** was removed from the active basket.",
            spoken_reply_english=speech_en,
            spoken_reply_tamil=speech_ta,
            spoken_reply_tanglish=speech_tgl,
            raw_transcript=text,
            action_payload={"action": "REMOVE_FROM_CART", "product_id": product.id, "product_name": product.name},
            data={"product_id": product.id, "product_name": product.name},
            suggestions=["What is the bill total?", "Clear the bill"],
        )

    @classmethod
    async def _handle_check_bill_total(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        speech_en = "You can view your current live bill in the POS Billing panel."
        speech_ta = "Current bill summary POS screen-la theriyum."
        speech_tgl = "Current bill details POS billing panel-la paakkalaam."

        return AssistantResponse(
            intent="CHECK_BILL_TOTAL",
            confidence_status="CONFIRMED",
            speech_text=speech_en,
            display_text="🧾 **POS Bill Status:** View itemized totals and charges in the Visual POS tab.",
            spoken_reply_english=speech_en,
            spoken_reply_tamil=speech_ta,
            spoken_reply_tanglish=speech_tgl,
            raw_transcript=text,
            action_payload={"action": "CHECK_BILL_TOTAL"},
            suggestions=["Add 2 Nandini milk to cart", "Clear the bill"],
        )

    @classmethod
    async def _handle_clear_bill(
        cls, db: AsyncSession, text: str, parsed: GeminiParsedIntent
    ) -> AssistantResponse:
        speech_en = "Are you sure you want to clear the entire bill? Please confirm to proceed or cancel."
        speech_ta = "Bill mothama clear panna porom. Confirm pannunga."
        speech_tgl = "Bill-a mothama clear panna porom. Sari-na confirm pannunga."

        return AssistantResponse(
            intent="CLEAR_BILL",
            confidence_status="CONFIRMED",
            requires_confirmation=True,
            speech_text=speech_en,
            display_text="⚠️ **Clear Bill Confirmation:** Are you sure you want to remove all items from the current counter bill?",
            spoken_reply_english=speech_en,
            spoken_reply_tamil=speech_ta,
            spoken_reply_tanglish=speech_tgl,
            raw_transcript=text,
            action_payload={"action": "CLEAR_BILL"},
            suggestions=["Aama, confirm pannu", "Cancel pannidu"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # E. CONFIRMED ACTIONS EXECUTOR (STRICT TRANSACTIONAL BOUNDARY)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _execute_confirmed_action(
        cls, db: AsyncSession, payload: Dict[str, Any]
    ) -> AssistantResponse:
        action = payload.get("action")

        if action == "CLEAR_BILL":
            return AssistantResponse(
                intent="CLEAR_BILL",
                speech_text="Current bill has been cleared.",
                display_text="🗑️ **Bill Cleared:** All items have been removed from the current basket.",
                spoken_reply_tamil="Bill mothama clear aaidichu.",
                spoken_reply_english="Current bill has been cleared.",
                spoken_reply_tanglish="Bill-a clear pannittaen.",
                action_payload={"action": "CLEAR_BILL_EXECUTED"},
            )

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
