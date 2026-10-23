"""
StockSense AI - Voice Assistant Service

Understands natural language commands for inventory checking, expiry inspection,
sales recording, stock receipts, and AI purchase recommendations.
Uses real PostgreSQL data and transactional services.
"""

import re
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
)
from app.services.inventory_service import InventoryService
from app.services.sales_service import SalesService
from app.services.reorder_engine import ReorderEngine
from app.services.budget_optimizer import BudgetOptimizer


WORD_TO_NUMBER = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000
}


def parse_number_from_text(text: str) -> Optional[Decimal]:
    """Extract quantity/number from text (words or digits)."""
    cleaned = text.replace(',', '')
    match = re.search(r'\b(\d+(?:\.\d+)?)\b', cleaned)
    if match:
        try:
            return Decimal(match.group(1))
        except Exception:
            pass
    
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    total = 0
    found_any = False
    current = 0
    for w in words:
        if w in WORD_TO_NUMBER:
            val = WORD_TO_NUMBER[w]
            found_any = True
            if val == 100 or val == 1000:
                current = (current if current > 0 else 1) * val
            else:
                current += val
        elif found_any:
            break
    total += current
    if found_any and total > 0:
        return Decimal(str(total))
    return None


def parse_date_from_text(text: str) -> Optional[date]:
    """Extract date if present like '30 October 2026' or '2026-10-30'."""
    text_lower = text.lower()
    today = date.today()
    if 'tomorrow' in text_lower:
        return today + timedelta(days=1)
    if 'today' in text_lower:
        return today
    
    iso_match = re.search(r'\b(20\d\d)-(\d{1,2})-(\d{1,2})\b', text)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except Exception:
            pass

    months = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
        'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
        'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
    }
    date_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)(?:\s+(\d{4}))?\b', text_lower)
    if date_match:
        d_str, m_str, y_str = date_match.groups()
        if m_str in months:
            m = months[m_str]
            d = int(d_str)
            y = int(y_str) if y_str else today.year
            try:
                return date(y, m, d)
            except Exception:
                pass
    return None


class AssistantService:
    """Service that parses and executes voice assistant commands against the database."""

    @staticmethod
    async def match_products(db: AsyncSession, text: str) -> List[Product]:
        """Find products matching the user's spoken words."""
        result = await db.execute(select(Product).where(Product.is_active == True))
        all_products = result.scalars().all()
        
        text_lower = text.lower()
        
        stop_words = {
            'how', 'much', 'many', 'stock', 'is', 'left', 'available', 'show', 'me',
            'the', 'remaining', 'of', 'in', 'are', 'there', 'what', 'we', 'i', 'sold',
            'sell', 'record', 'a', 'sale', 'new', 'received', 'add', 'to', 'batch',
            'expiring', 'on', 'first', 'which', 'bags', 'packets', 'packet', 'bag',
            'kg', 'litres', 'bottle', 'piece', 'box', 'boxes', 'tin', 'can', 'please',
            'for', 'and', 'with', 'from', 'at'
        }
        
        cleaned_words = [w for w in re.findall(r'\b[a-zA-Z0-9]+\b', text_lower) if w not in stop_words and len(w) > 2]
        
        matches = []
        for p in all_products:
            p_name_lower = p.name.lower()
            score = 0
            for word in cleaned_words:
                if word in p_name_lower:
                    score += 2 if len(word) > 3 else 1
            if score > 0:
                matches.append((p, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        unique_matches = []
        seen_ids = set()
        for p, _ in matches:
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                unique_matches.append(p)
        
        return unique_matches

    @classmethod
    async def process_command(
        cls,
        db: AsyncSession,
        command_text: str,
        confirmed: bool = False,
        action_payload: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> AssistantResponse:
        """Main entrypoint: parses intent and routes to executor."""
        text = command_text.strip()
        text_lower = text.lower()

        # Confirmation callback
        if confirmed and action_payload:
            return await cls._execute_confirmed_action(db, action_payload)

        # ─── E. SALES & BUSINESS INFO ───
        if any(phrase in text_lower for phrase in [
            'how much did i sell', "today's sales", 'todays sales', 'sold today',
            'sold the most', 'most sold', 'top selling', 'not sold recently',
            'slow moving', 'sales today', 'today sales', 'sales this week', 'how much sold'
        ]):
            return await cls._handle_sales_info(db, text)

        # ─── C. RECORD A SALE ───
        if any(k in text_lower for k in ['record a sale', 'i sold', 'sell ', 'sold ', 'sale of']):
            return await cls._handle_record_sale(db, text, confirmed)

        # ─── D. RECEIVE NEW STOCK ───
        if any(k in text_lower for k in ['received', 'add to stock', 'new stock', 'receive stock', 'record a new batch', 'add ']) and any(k in text_lower for k in ['stock', 'received', 'batch', 'packets', 'bags', 'kg']):
            return await cls._handle_receive_stock(db, text, confirmed)

        # ─── B. CHECK EXPIRY DATES ───
        if any(k in text_lower for k in ['expire', 'expiry', 'expiring', 'expired']):
            return await cls._handle_expiry_queries(db, text)

        # ─── F. AI PURCHASE RECOMMENDATIONS & BUDGET ───
        if any(k in text_lower for k in ['reorder', 'recommend', 'budget', 'run out soon', 'why are you recommending', 'worth purchasing']):
            return await cls._handle_reorder_recommendations(db, text)

        # ─── A. CHECK INVENTORY ───
        if any(phrase in text_lower for phrase in [
            'how much', 'how many', 'stock is left', 'remaining stock', 'stock of', 'available stock', 'stock left'
        ]) and not any(k in text_lower for k in ['expire', 'sold', 'sale', 'sell', 'received', 'reorder', 'purchase']):
            return await cls._handle_check_stock(db, text)

        # Low stock check
        if any(phrase in text_lower for phrase in ['running low', 'low stock', 'low on stock', 'need restock']):
            return await cls._handle_low_stock(db)

        # Out of stock check
        if any(phrase in text_lower for phrase in ['out of stock', 'zero stock', 'no stock', 'empty stock']):
            return await cls._handle_out_of_stock(db)

        # ─── F. AI PURCHASE RECOMMENDATIONS & BUDGET ───
        if any(k in text_lower for k in ['reorder', 'recommend', 'budget', 'run out soon', 'why are you recommending', 'worth purchasing']):
            return await cls._handle_reorder_recommendations(db, text)

        # Fallback: Try product match directly
        matched_products = await cls.match_products(db, text)
        if matched_products:
            return await cls._handle_check_stock(db, text)

        return AssistantResponse(
            intent='UNKNOWN',
            speech_text="I did not quite understand that. You can ask me to check stock, view expiring products, record a sale, or get reorder recommendations.",
            display_text="I couldn't identify the requested action. Try asking one of the suggestions below.",
            suggestions=[
                "How much rice stock is left?",
                "Which products expire tomorrow?",
                "Record a sale of 2 milk packets",
                "What should I reorder today?",
                "Which products are running low?"
            ]
        )

    # ──────────────────────────────────────────────────────────────────────────
    # A. INVENTORY HANDLERS
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_check_stock(cls, db: AsyncSession, text: str) -> AssistantResponse:
        matched = await cls.match_products(db, text)
        if not matched:
            return AssistantResponse(
                intent='CHECK_STOCK',
                speech_text="I couldn't find any product matching that name in your inventory.",
                display_text="No matching product found in database. Please specify the exact product name.",
                suggestions=["How much rice stock is left?", "Show all products currently out of stock"]
            )
        
        product = matched[0]
        today = date.today()
        usable_stock = await InventoryService.get_usable_stock(db, product.id, today)
        total_stock = await InventoryService.get_total_stock(db, product.id)
        
        status_label = 'In stock'
        if usable_stock <= 0:
            status_label = 'Out of stock'
        elif usable_stock <= product.reorder_threshold:
            status_label = 'Low stock'

        qty_formatted = int(usable_stock) if usable_stock % 1 == 0 else float(usable_stock)
        unit_str = product.unit if qty_formatted == 1 else f"{product.unit}s"

        speech = f"The current stock of {product.name} is {qty_formatted} {unit_str}."
        display = f"**Product:** {product.name}\n**Available stock:** {qty_formatted} {unit_str}\n**Stock status:** {status_label}"

        stock_info = StockInfo(
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            unit=product.unit,
            usable_stock=usable_stock,
            total_stock=total_stock,
            reorder_threshold=product.reorder_threshold,
            status=status_label
        )

        first_word = product.name.split()[0]
        return AssistantResponse(
            intent='CHECK_STOCK',
            speech_text=speech,
            display_text=display,
            data=stock_info.model_dump(),
            suggestions=[
                f"Record a sale of 2 {product.unit}s of {first_word}",
                f"Which batch of {first_word} expires first?",
                "Which products are running low?"
            ]
        )

    @classmethod
    async def _handle_low_stock(cls, db: AsyncSession) -> AssistantResponse:
        today = date.today()
        res = await db.execute(select(Product).where(Product.is_active == True))
        products = res.scalars().all()

        low_items = []
        for p in products:
            usable = await InventoryService.get_usable_stock(db, p.id, today)
            if 0 < usable <= p.reorder_threshold:
                low_items.append({
                    'product_id': p.id,
                    'product_name': p.name,
                    'sku': p.sku,
                    'usable_stock': float(usable),
                    'reorder_threshold': float(p.reorder_threshold),
                    'unit': p.unit,
                })

        if not low_items:
            return AssistantResponse(
                intent='CHECK_LOW_STOCK',
                speech_text="Good news! There are currently no products running low on stock.",
                display_text="All active products have adequate stock above their reorder thresholds.",
                data=[]
            )

        speech = f"There are {len(low_items)} products running low on stock, including {low_items[0]['product_name']}."
        display = f"**{len(low_items)} Products Running Low:**\n" + "\n".join([
            f"- **{item['product_name']}**: {item['usable_stock']} {item['unit']} (Threshold: {item['reorder_threshold']})"
            for item in low_items
        ])

        return AssistantResponse(
            intent='CHECK_LOW_STOCK',
            speech_text=speech,
            display_text=display,
            data=low_items,
            suggestions=["What should I reorder today?", "Show all products currently out of stock"]
        )

    @classmethod
    async def _handle_out_of_stock(cls, db: AsyncSession) -> AssistantResponse:
        today = date.today()
        res = await db.execute(select(Product).where(Product.is_active == True))
        products = res.scalars().all()

        out_items = []
        for p in products:
            usable = await InventoryService.get_usable_stock(db, p.id, today)
            if usable <= 0:
                out_items.append({
                    'product_id': p.id,
                    'product_name': p.name,
                    'sku': p.sku,
                    'usable_stock': 0,
                    'unit': p.unit,
                })

        if not out_items:
            return AssistantResponse(
                intent='CHECK_OUT_OF_STOCK',
                speech_text="All products currently have stock available. None are out of stock.",
                display_text="No products are currently out of stock.",
                data=[]
            )

        speech = f"{len(out_items)} products are currently out of stock, including {out_items[0]['product_name']}."
        display = f"**{len(out_items)} Products Out of Stock:**\n" + "\n".join([
            f"- **{item['product_name']}** (SKU: {item['sku']})"
            for item in out_items
        ])

        return AssistantResponse(
            intent='CHECK_OUT_OF_STOCK',
            speech_text=speech,
            display_text=display,
            data=out_items,
            suggestions=["What should I reorder today?", "Which products are running low?"]
        )

    # ──────────────────────────────────────────────────────────────────────────
    # B. EXPIRY HANDLERS
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_expiry_queries(cls, db: AsyncSession, text: str) -> AssistantResponse:
        today = date.today()
        text_lower = text.lower()

        # Earliest batch of a specific product
        if 'first' in text_lower or 'earliest' in text_lower:
            matched = await cls.match_products(db, text)
            if matched:
                product = matched[0]
                result = await db.execute(
                    select(InventoryBatch)
                    .where(
                        InventoryBatch.product_id == product.id,
                        InventoryBatch.remaining_quantity > 0,
                        InventoryBatch.expiry_date.isnot(None)
                    )
                    .order_by(InventoryBatch.expiry_date.asc())
                    .limit(1)
                )
                earliest_batch = result.scalar_one_or_none()
                if earliest_batch:
                    days_left = (earliest_batch.expiry_date - today).days
                    days_str = "today" if days_left == 0 else f"in {days_left} days" if days_left > 0 else f"{abs(days_left)} days ago"
                    speech = f"The earliest expiring batch of {product.name} is Batch {earliest_batch.batch_number}, expiring {days_str} on {earliest_batch.expiry_date}. It has {earliest_batch.remaining_quantity} {product.unit}s remaining."
                    display = (
                        f"**Earliest Batch for {product.name}:**\n"
                        f"- Batch Number: `{earliest_batch.batch_number}`\n"
                        f"- Expiry Date: **{earliest_batch.expiry_date}** ({days_str})\n"
                        f"- Remaining Quantity: **{earliest_batch.remaining_quantity} {product.unit}**\n"
                        f"- Order: FEFO Priority #1"
                    )
                    return AssistantResponse(
                        intent='CHECK_EXPIRY',
                        speech_text=speech,
                        display_text=display,
                        data={
                            'batch_number': earliest_batch.batch_number,
                            'product_name': product.name,
                            'remaining_quantity': float(earliest_batch.remaining_quantity),
                            'expiry_date': str(earliest_batch.expiry_date),
                            'days_left': days_left
                        }
                    )
                else:
                    return AssistantResponse(
                        intent='CHECK_EXPIRY',
                        speech_text=f"There are no expiring batches with recorded dates for {product.name}.",
                        display_text=f"No expiry date tracked for current batches of {product.name}."
                    )

        # Expired products
        if 'expired' in text_lower and not any(k in text_lower for k in ['tomorrow', 'seven', '7', 'days']):
            result = await db.execute(
                select(InventoryBatch, Product)
                .join(Product, InventoryBatch.product_id == Product.id)
                .where(
                    InventoryBatch.remaining_quantity > 0,
                    InventoryBatch.expiry_date <= today
                )
                .order_by(InventoryBatch.expiry_date.desc())
            )
            rows = result.all()
            if not rows:
                return AssistantResponse(
                    intent='CHECK_EXPIRY',
                    speech_text="Great news! There are zero expired products in stock.",
                    display_text="No batches have expired.",
                    data=[]
                )
            
            speech = f"There are {len(rows)} expired batches in stock. The oldest is {rows[0][1].name}."
            display = f"**{len(rows)} Expired Batches in Stock:**\n" + "\n".join([
                f"- **{p.name}** (Batch: `{b.batch_number}`): {b.remaining_quantity} {p.unit} expired on {b.expiry_date}"
                for b, p in rows
            ])
            return AssistantResponse(
                intent='CHECK_EXPIRY',
                speech_text=speech,
                display_text=display,
                data=[{
                    'batch_number': b.batch_number,
                    'product_name': p.name,
                    'quantity': float(b.remaining_quantity),
                    'unit': p.unit,
                    'expiry_date': str(b.expiry_date),
                    'status': 'Expired'
                } for b, p in rows]
            )

        # Products expiring tomorrow
        if 'tomorrow' in text_lower or '1 day' in text_lower:
            target_date = today + timedelta(days=1)
            result = await db.execute(
                select(InventoryBatch, Product)
                .join(Product, InventoryBatch.product_id == Product.id)
                .where(
                    InventoryBatch.remaining_quantity > 0,
                    InventoryBatch.expiry_date == target_date
                )
                .order_by(InventoryBatch.expiry_date.asc())
            )
            rows = result.all()
            if not rows:
                return AssistantResponse(
                    intent='CHECK_EXPIRY',
                    speech_text="No products expire tomorrow.",
                    display_text=f"No inventory batches expire tomorrow ({target_date}).",
                    data=[]
                )
            
            pnames = ", ".join([f"{b.remaining_quantity} {p.unit} of {p.name}" for b, p in rows])
            speech = f"Expiring tomorrow: {pnames}."
            display = f"**Batches Expiring Tomorrow ({target_date}):**\n" + "\n".join([
                f"- **{p.name}** (Batch `{b.batch_number}`): {b.remaining_quantity} {p.unit}"
                for b, p in rows
            ])
            return AssistantResponse(
                intent='CHECK_EXPIRY',
                speech_text=speech,
                display_text=display,
                data=[{
                    'batch_number': b.batch_number,
                    'product_name': p.name,
                    'quantity': float(b.remaining_quantity),
                    'unit': p.unit,
                    'expiry_date': str(b.expiry_date),
                    'status': 'Expiring Tomorrow'
                } for b, p in rows]
            )

        # Default: Next 7 days
        days = 7
        end_date = today + timedelta(days=days)
        result = await db.execute(
            select(InventoryBatch, Product)
            .join(Product, InventoryBatch.product_id == Product.id)
            .where(
                InventoryBatch.remaining_quantity > 0,
                InventoryBatch.expiry_date >= today,
                InventoryBatch.expiry_date <= end_date
            )
            .order_by(InventoryBatch.expiry_date.asc())
        )
        rows = result.all()
        if not rows:
            return AssistantResponse(
                intent='CHECK_EXPIRY',
                speech_text=f"No products are scheduled to expire in the next {days} days.",
                display_text=f"No batches expiring between {today} and {end_date}.",
                data=[]
            )
        
        speech = f"There are {len(rows)} batches expiring in the next {days} days, including {rows[0][1].name}."
        display = f"**Batches Expiring in the Next {days} Days (FEFO Priority):**\n" + "\n".join([
            f"- **{p.name}** (Batch `{b.batch_number}`): {b.remaining_quantity} {p.unit} expires on {b.expiry_date}"
            for b, p in rows
        ])
        return AssistantResponse(
            intent='CHECK_EXPIRY',
            speech_text=speech,
            display_text=display,
            data=[{
                'batch_number': b.batch_number,
                'product_name': p.name,
                'quantity': float(b.remaining_quantity),
                'unit': p.unit,
                'expiry_date': str(b.expiry_date),
                'days_left': (b.expiry_date - today).days,
                'status': 'Expiring Soon'
            } for b, p in rows]
        )

    # ──────────────────────────────────────────────────────────────────────────
    # C. RECORD A SALE
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_record_sale(cls, db: AsyncSession, text: str, confirmed: bool) -> AssistantResponse:
        matched = await cls.match_products(db, text)
        if not matched:
            return AssistantResponse(
                intent='RECORD_SALE',
                speech_text="I couldn't identify which product you want to sell. Please specify the product name.",
                display_text="Product not identified. Example: 'Record a sale of 2 milk packets'",
                suggestions=["Record a sale of 2 milk packets", "I sold 5 bags of rice"]
            )

        product = matched[0]
        qty = parse_number_from_text(text) or Decimal('1')

        # Check stock availability
        today = date.today()
        usable_stock = await InventoryService.get_usable_stock(db, product.id, today)
        if usable_stock < qty:
            speech = f"Cannot record sale. Only {usable_stock} {product.unit} of {product.name} are available in usable stock, but you requested {qty}."
            display = f"**Insufficient Stock!**\nRequested: {qty} {product.unit}\nAvailable: {usable_stock} {product.unit}\nProduct: {product.name}"
            return AssistantResponse(
                intent='RECORD_SALE',
                speech_text=speech,
                display_text=display,
                error='INSUFFICIENT_STOCK'
            )

        line_total = qty * product.selling_price
        unit_str = product.unit if qty == 1 else f"{product.unit}s"

        speech_prompt = f"Record a sale of {int(qty) if qty % 1 == 0 else qty} {unit_str} of {product.name} for {int(line_total)} rupees?"
        display_prompt = (
            f"### Confirm Sale Transaction\n"
            f"- **Product:** {product.name}\n"
            f"- **Quantity:** {qty} {unit_str}\n"
            f"- **Unit Price:** ₹{product.selling_price}\n"
            f"- **Total Amount:** ₹{line_total}\n"
            f"- **Remaining Usable Stock After Sale:** {usable_stock - qty} {unit_str}\n\n"
            f"*Do you want to confirm and complete this sale?*"
        )

        action_payload = {
            'action': 'RECORD_SALE',
            'product_id': product.id,
            'product_name': product.name,
            'quantity': float(qty),
            'unit': product.unit,
            'unit_price': float(product.selling_price),
            'line_total': float(line_total)
        }

        return AssistantResponse(
            intent='RECORD_SALE',
            speech_text=speech_prompt,
            display_text=display_prompt,
            requires_confirmation=True,
            action_payload=action_payload,
            data=action_payload
        )

    # ──────────────────────────────────────────────────────────────────────────
    # D. RECEIVE NEW STOCK
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_receive_stock(cls, db: AsyncSession, text: str, confirmed: bool) -> AssistantResponse:
        matched = await cls.match_products(db, text)
        if not matched:
            return AssistantResponse(
                intent='RECEIVE_STOCK',
                speech_text="I couldn't identify which product to add stock for. Please specify the product name.",
                display_text="Product not found. Example: 'We received 20 biscuit packets'",
                suggestions=["We received 20 biscuit packets", "Add 10 bags of rice to stock"]
            )

        product = matched[0]
        qty = parse_number_from_text(text) or Decimal('10')
        expiry = parse_date_from_text(text)

        if not expiry and product.shelf_life_days:
            expiry = date.today() + timedelta(days=product.shelf_life_days)

        unit_str = product.unit if qty == 1 else f"{product.unit}s"
        batch_number = f"BAT-{datetime.now().strftime('%y%m%d%H%M')}"

        speech_prompt = f"Add {int(qty) if qty % 1 == 0 else qty} {unit_str} of {product.name} to stock?"
        display_prompt = (
            f"### Confirm Inbound Stock Receipt\n"
            f"- **Product:** {product.name}\n"
            f"- **Quantity:** {qty} {unit_str}\n"
            f"- **Unit Cost:** ₹{product.purchase_cost}\n"
            f"- **Batch Number:** `{batch_number}`\n"
            f"- **Expiry Date:** {expiry or 'Not Specified'}\n\n"
            f"*Do you want to confirm and receive this stock?*"
        )

        action_payload = {
            'action': 'RECEIVE_STOCK',
            'product_id': product.id,
            'product_name': product.name,
            'quantity': float(qty),
            'unit': product.unit,
            'unit_cost': float(product.purchase_cost),
            'batch_number': batch_number,
            'expiry_date': str(expiry) if expiry else None
        }

        return AssistantResponse(
            intent='RECEIVE_STOCK',
            speech_text=speech_prompt,
            display_text=display_prompt,
            requires_confirmation=True,
            action_payload=action_payload,
            data=action_payload
        )

    # ──────────────────────────────────────────────────────────────────────────
    # CONFIRMED ACTIONS EXECUTOR
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _execute_confirmed_action(cls, db: AsyncSession, payload: Dict[str, Any]) -> AssistantResponse:
        action = payload.get('action')

        if action == 'RECORD_SALE':
            product_id = payload['product_id']
            qty = Decimal(str(payload['quantity']))
            unit_price = Decimal(str(payload['unit_price']))

            item = SaleItemCreate(
                product_id=product_id,
                quantity=qty,
                unit_price=unit_price
            )
            try:
                sale = await SalesService.create_sale(
                    db=db,
                    items=[item],
                    notes="Recorded via StockSense Voice Assistant"
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                return AssistantResponse(
                    intent='RECORD_SALE',
                    speech_text=f"Failed to record sale: {str(e)}",
                    display_text=f"Transaction error: {str(e)}",
                    error=str(e)
                )

            speech = f"Sale recorded successfully for {payload['quantity']} {payload['unit']} of {payload['product_name']}. Receipt number is {sale.sale_number}."
            display = (
                f"### Sale Completed Successfully\n"
                f"- **Sale Number:** `{sale.sale_number}`\n"
                f"- **Product:** {payload['product_name']}\n"
                f"- **Quantity Deducted:** {payload['quantity']} {payload['unit']} (FEFO order)\n"
                f"- **Total Amount:** ₹{payload['line_total']}\n"
                f"- **Status:** COMPLETED & SAVED TO LEDGER"
            )
            return AssistantResponse(
                intent='RECORD_SALE',
                speech_text=speech,
                display_text=display,
                data={'sale_number': sale.sale_number, 'total_amount': payload['line_total']}
            )

        elif action == 'RECEIVE_STOCK':
            product_id = payload['product_id']
            qty = Decimal(str(payload['quantity']))
            unit_cost = Decimal(str(payload['unit_cost']))
            batch_num = payload.get('batch_number')
            expiry_str = payload.get('expiry_date')
            expiry_date = date.fromisoformat(expiry_str) if expiry_str else None

            try:
                batch, movement = await InventoryService.create_stock_receipt(
                    db=db,
                    product_id=product_id,
                    quantity=qty,
                    unit_cost=unit_cost,
                    batch_number=batch_num,
                    expiry_date=expiry_date,
                    source_type='DIRECT',
                    notes="Received via StockSense Voice Assistant"
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                return AssistantResponse(
                    intent='RECEIVE_STOCK',
                    speech_text=f"Failed to receive stock: {str(e)}",
                    display_text=f"Stock receipt error: {str(e)}",
                    error=str(e)
                )

            speech = f"Stock received! Added {payload['quantity']} {payload['unit']} of {payload['product_name']} under batch {batch.batch_number}."
            display = (
                f"### Stock Received & Ledger Updated\n"
                f"- **Product:** {payload['product_name']}\n"
                f"- **Quantity Added:** +{payload['quantity']} {payload['unit']}\n"
                f"- **Batch Number:** `{batch.batch_number}`\n"
                f"- **Expiry Date:** {expiry_date or 'None'}\n"
                f"- **Status:** COMMITTED TO INVENTORY"
            )
            return AssistantResponse(
                intent='RECEIVE_STOCK',
                speech_text=speech,
                display_text=display,
                data={'batch_number': batch.batch_number, 'quantity_added': float(qty)}
            )

        return AssistantResponse(
            intent='UNKNOWN',
            speech_text="Unknown action payload.",
            display_text="Unknown confirmed action."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # E. SALES & BUSINESS INFO
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_sales_info(cls, db: AsyncSession, text: str) -> AssistantResponse:
        today = date.today()
        text_lower = text.lower()

        # Top selling product this week
        if 'most' in text_lower or 'top' in text_lower:
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            res = await db.execute(
                select(Product.name, func.sum(SaleItem.quantity).label('qty_sold'))
                .join(Product, SaleItem.product_id == Product.id)
                .join(Sale, SaleItem.sale_id == Sale.id)
                .where(Sale.sale_date >= week_ago, Sale.status == 'COMPLETED')
                .group_by(Product.name)
                .order_by(desc('qty_sold'))
                .limit(1)
            )
            top = res.first()
            if top:
                speech = f"The top selling product this week is {top[0]} with {top[1]} units sold."
                display = f"**Top Selling Product This Week:**\n- **{top[0]}**: {top[1]} units sold"
            else:
                speech = "No sales recorded in the past week."
                display = "No completed sales in the past 7 days."
            return AssistantResponse(intent='SALES_INFO', speech_text=speech, display_text=display)

        # Products not sold recently
        if 'not sold' in text_lower or 'slow' in text_lower:
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            sold_subq = select(SaleItem.product_id).join(Sale, SaleItem.sale_id == Sale.id).where(Sale.sale_date >= thirty_days_ago).scalar_subquery()
            res = await db.execute(
                select(Product)
                .where(Product.is_active == True, Product.id.notin_(sold_subq))
                .limit(5)
            )
            non_sellers = res.scalars().all()
            if non_sellers:
                names = ", ".join([p.name for p in non_sellers])
                speech = f"These products have not sold in the last 30 days: {names}."
                display = f"**Slow-Moving Products (No sales in 30 days):**\n" + "\n".join([f"- {p.name}" for p in non_sellers])
            else:
                speech = "All active products have had sales recorded recently."
                display = "All active products have recorded sales in the last 30 days."
            return AssistantResponse(intent='SALES_INFO', speech_text=speech, display_text=display)

        # Today's sales
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
        res = await db.execute(
            select(
                func.coalesce(func.sum(Sale.total_amount), Decimal('0')),
                func.count(Sale.id)
            )
            .where(Sale.sale_date >= today_start, Sale.status == 'COMPLETED')
        )
        total_amt, count = res.first() or (Decimal('0'), 0)
        amt_int = int(total_amt)

        speech = f"Today's sales total is {amt_int} rupees across {count} transactions."
        display = (
            f"### Today's Sales Performance\n"
            f"- **Total Revenue:** ₹{total_amt:,.2f}\n"
            f"- **Completed Transactions:** {count}\n"
            f"- **Date:** {today}"
        )
        return AssistantResponse(
            intent='SALES_INFO',
            speech_text=speech,
            display_text=display,
            data={'total_sales': float(total_amt), 'total_transactions': count}
        )

    # ──────────────────────────────────────────────────────────────────────────
    # F. AI PURCHASE RECOMMENDATIONS & BUDGET
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    async def _handle_reorder_recommendations(cls, db: AsyncSession, text: str) -> AssistantResponse:
        text_lower = text.lower()

        # Explanation for a specific product
        if 'why' in text_lower:
            matched = await cls.match_products(db, text)
            if matched:
                product = matched[0]
                usable = await InventoryService.get_usable_stock(db, product.id)
                speech = f"We recommend reordering {product.name} because current stock is {usable} {product.unit}s, which is close to or below the safety threshold of {product.reorder_threshold} {product.unit}s with a supplier lead time of {product.supplier_lead_time_days} days."
                display = (
                    f"### AI Recommendation Explanation for {product.name}\n"
                    f"- **Current Usable Stock:** {usable} {product.unit}\n"
                    f"- **Reorder Threshold:** {product.reorder_threshold} {product.unit}\n"
                    f"- **Safety Stock Target:** {product.safety_stock} {product.unit}\n"
                    f"- **Supplier Lead Time:** {product.supplier_lead_time_days} days\n"
                    f"- **Rationale:** Ordering now prevents a stockout before the next shipment arrives."
                )
                return AssistantResponse(intent='AI_RECOMMENDATION', speech_text=speech, display_text=display)

        # Budget-aware optimization
        budget_match = re.search(r'budget\s*(?:of)?\s*(?:rs\.?|rupees)?\s*(\d+(?:,\d+)?(?:\.\d+)?)', text_lower) or \
                       re.search(r'(\d+(?:,\d+)?)\s*(?:rs|rupees|inr)\s*budget', text_lower)
        if budget_match or 'budget' in text_lower:
            budget_val = Decimal('2000')
            if budget_match:
                budget_val = Decimal(budget_match.group(1).replace(',', ''))
            
            try:
                plan = await BudgetOptimizer.create_budget_plan(db, budget_val)
                items = plan.items
                if items:
                    # Get product names
                    p_ids = [item.product_id for item in items]
                    p_res = await db.execute(select(Product).where(Product.id.in_(p_ids)))
                    prod_map = {p.id: p for p in p_res.scalars().all()}

                    speech = f"With a budget of {int(budget_val)} rupees, StockSense recommends purchasing {len(items)} items for an allocated total of {int(plan.total_allocated)} rupees."
                    display = f"### AI Budget Optimization Plan (Budget: ₹{budget_val:,.2f})\n" + "\n".join([
                        f"- **{prod_map[item.product_id].name if item.product_id in prod_map else 'Product'}**: {item.suggested_quantity} units (~₹{item.line_cost:,.2f}) - {item.priority or 'HIGH'} priority"
                        for item in items
                    ]) + f"\n\n**Total Allocated:** ₹{plan.total_allocated:,.2f} | **Remaining Budget:** ₹{plan.remaining_budget:,.2f}"
                    return AssistantResponse(
                        intent='AI_RECOMMENDATION',
                        speech_text=speech,
                        display_text=display,
                        data=[{
                            'product_name': prod_map[item.product_id].name if item.product_id in prod_map else f"Product {item.product_id}",
                            'quantity': float(item.suggested_quantity),
                            'line_total': float(item.line_cost),
                            'unit_cost': float(item.unit_cost)
                        } for item in items]
                    )
            except Exception as e:
                pass

        # General Reorder recommendations
        recs = await ReorderEngine.calculate_recommendations(db)
        actionable = [r for r in recs if r.suggested_quantity and r.suggested_quantity > 0]

        if not actionable:
            return AssistantResponse(
                intent='AI_RECOMMENDATION',
                speech_text="Stock levels are healthy across all products. No reorders needed today.",
                display_text="All active products have adequate stock coverage. No reorders recommended.",
                data=[]
            )

        # Map product names
        p_ids = [r.product_id for r in actionable]
        p_res = await db.execute(select(Product).where(Product.id.in_(p_ids)))
        prod_map = {p.id: p for p in p_res.scalars().all()}

        top_recs = actionable[:4]
        items_summary = ", ".join([f"{int(r.suggested_quantity)} units of {prod_map[r.product_id].name if r.product_id in prod_map else 'item'}" for r in top_recs[:2]])
        speech = f"StockSense recommends reordering {len(actionable)} products today, including {items_summary}."
        display = f"### AI Reorder Recommendations ({len(actionable)} items)\n" + "\n".join([
            f"- **{prod_map[r.product_id].name if r.product_id in prod_map else 'Item'}**: Reorder **{r.suggested_quantity} {prod_map[r.product_id].unit if r.product_id in prod_map else 'units'}** (Est. Cost: ₹{r.estimated_cost:,.2f})"
            for r in top_recs
        ])

        return AssistantResponse(
            intent='AI_RECOMMENDATION',
            speech_text=speech,
            display_text=display,
            data=[{
                'product_id': r.product_id,
                'product_name': prod_map[r.product_id].name if r.product_id in prod_map else f"Product {r.product_id}",
                'suggested_quantity': float(r.suggested_quantity),
                'unit': prod_map[r.product_id].unit if r.product_id in prod_map else 'unit',
                'estimated_cost': float(r.estimated_cost),
                'explanation': r.explanation,
                'priority': r.priority
            } for r in top_recs],
            suggestions=["Recommend purchases within my 2,000 rupee budget", "Why are you recommending more rice?"]
        )
