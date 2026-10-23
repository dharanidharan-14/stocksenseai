"""
StockSense AI - Gemini Intent Parser Service

Uses the official Google GenAI SDK with structured Pydantic schemas to convert
natural language voice and typed queries (English, Tamil, Tanglish, and local slang)
into typed intents for inventory querying and transactional operations.
"""

import json
import logging
import time
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from app.core.config import settings
from app.schemas.assistant import GeminiParsedIntent

logger = logging.getLogger("stocksense.assistant.gemini")

SYSTEM_INSTRUCTION = """You are the AI Inventory Engine for StockSense AI, a smart Kirana (grocery store) operating in Tamil Nadu, India.
Your job is to understand shopkeeper speech and text in English, Tamil script, Tanglish, and local Bazaar slang.

CRITICAL INVENTORY CAPABILITY BOUNDARIES:
The StockSense AI application ONLY supports the following backend operations:
1. CHECK_STOCK: Checking quantity or availability of a specific product (e.g. 'Tomato stock la evlo irukku?', 'Do we have sugar?').
2. CHECK_LOW_STOCK: Checking products running low or near reorder thresholds (e.g. 'Enna items kammiya irukku?').
3. CHECK_OUT_OF_STOCK: Checking zero usable stock items (e.g. 'Theendhu pona items enna?').
4. CHECK_EXPIRY: Checking batches expiring soon or expired (e.g. 'Naalaiku expire aagura items enna?').
5. SALES_INFO: Inquiries about turnover, revenue, or items sold today/this week (e.g. 'Innaiku sales evlo?').
6. AI_RECOMMENDATION: Asking what to purchase or asking for budget purchase advice (e.g. '2000 rooba budget la enna vaanganum?').
7. RECEIVE_STOCK: Receiving new inventory batches (e.g. '10 kilo tomato vandhuruchu', 'We received 20 packets milk').
8. RECORD_SALE: Recording customer sales at the counter (e.g. '5 packet biscuit sale panniten', 'Sold 2 packets milk').
9. CONFIRMATION: Confirming a pending proposal ('Aama', 'Yes', 'Confirm pannu', 'Sari', 'Proceed').
10. CANCELLATION: Cancelling/aborting a proposal ('Cancel pannidu', 'Vendaam', 'Stop', 'No').
11. CORRECTION: Modifying quantity/unit of pending proposal ('Illa, 5 illa 3 packet', 'Actually 10 kg mattum').

EXPLICITLY UNSUPPORTED OPERATIONS (MUST BE CLASSIFIED ACCORDINGLY):
- DISCOUNT_OR_OFFER: Asking to add, remove, calculate, or modify discounts, promotional offers, percentage off, or coupon deals (e.g. 'Remove the 20 percent offer on this product', 'Give 10% discount on dal').
  -> Set intent="DISCOUNT_OR_OFFER", is_supported=False, discount_percent=<extracted number if present>, unsupported_reason="Discount and promotional offer management is not supported in this application. No changes have been made to prices or inventory."
- PRICE_MODIFICATION: Changing selling prices or purchase costs (e.g. 'Change price of tomato to 40', 'Vilai maathu').
  -> Set intent="PRICE_MODIFICATION", is_supported=False, unsupported_reason="Modifying prices via voice is not supported. Please edit prices in the product catalog."
- UNSUPPORTED: Any other operation outside the supported Kirana inventory features (e.g. customer credit/khata ledger, employee management, store deletion).
  -> Set intent="UNSUPPORTED", is_supported=False, unsupported_reason="This operation is not supported by the inventory application."
- UNKNOWN: Irrelevant, ambiguous, or unintelligible input.
  -> Set intent="UNKNOWN", is_supported=False.

IMPORTANT ENTITY & PARAMETER RULES:
- NEVER FABRICATE OR GUESS QUANTITIES:
  If a user says 'Record a sale of milk' or 'We received tomato' without stating an explicit quantity, set quantity=null and add 'quantity' to missing_parameters.
- NEVER FABRICATE PRODUCTS:
  If user says 'Remove the 20 percent offer on this product' or 'Record sale of 2 packets' without stating which product, set product_raw=null and add 'product' to missing_parameters.
- DO NOT DEFAULT TO CHECK_STOCK:
  Never classify a discount, offer, price change, or unknown phrase as CHECK_STOCK just because a product name or number is present.
"""


class GeminiParserService:
    """Service wrapper for Google GenAI SDK intent parsing with fallback and retry."""

    _client: Optional[genai.Client] = None

    @classmethod
    def get_client(cls) -> Optional[genai.Client]:
        if cls._client is None and settings.GEMINI_API_KEY:
            try:
                cls._client = genai.Client(
                    api_key=settings.GEMINI_API_KEY,
                    http_options=types.HttpOptions(timeout=15000),  # 15s timeout
                )
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI Client: {e}")
                cls._client = None
        return cls._client

    @classmethod
    async def parse_intent(
        cls,
        text: str,
        context_history: Optional[List[Dict[str, str]]] = None,
    ) -> GeminiParsedIntent:
        """
        Parses natural language input into structured GeminiParsedIntent.
        Handles retries for 503 high demand and falls back to flash-lite if needed.
        """
        client = cls.get_client()
        if not client or not settings.GEMINI_API_KEY:
            logger.warning("Gemini API key not configured. Using rule-based fallback parser.")
            return cls._heuristic_fallback(text)

        # Prepare prompt with optional recent context
        prompt_parts = []
        if context_history:
            history_text = "\n".join(
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in context_history[-4:]
            )
            prompt_parts.append(f"Recent Conversation Context:\n{history_text}\n")

        prompt_parts.append(f"User Input: \"{text.strip()}\"")
        prompt_content = "\n".join(prompt_parts)

        primary_model = settings.GEMINI_MODEL or "gemini-3.5-flash"
        fallback_model = "gemini-3.5-flash-lite"

        # Attempt with primary model (with retry), then fallback model
        models_to_try = [primary_model]
        if fallback_model not in models_to_try:
            models_to_try.append(fallback_model)

        last_error = None

        for model_name in models_to_try:
            for attempt in range(2):  # up to 2 attempts per model for transient 503/504
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt_content,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            response_mime_type="application/json",
                            response_schema=GeminiParsedIntent,
                            temperature=0.1,
                        ),
                    )

                    if response.text:
                        data = json.loads(response.text)
                        parsed = GeminiParsedIntent(**data)
                        return parsed

                except genai_errors.APIError as api_err:
                    last_error = api_err
                    # 503 UNAVAILABLE or 504 DEADLINE_EXCEEDED -> brief wait and retry
                    if getattr(api_err, "code", None) in [503, 504] or "UNAVAILABLE" in str(api_err):
                        logger.warning(
                            f"Model {model_name} high demand/timeout (attempt {attempt+1}): {api_err}. Retrying in 1s..."
                        )
                        time.sleep(1.0)
                        continue
                    elif getattr(api_err, "code", None) == 429:
                        logger.warning(f"Rate limit 429 on {model_name}: {api_err}")
                        break  # switch to fallback model
                    else:
                        logger.error(f"Gemini API error on {model_name}: {api_err}")
                        break
                except Exception as e:
                    last_error = e
                    logger.error(f"Unexpected error calling Gemini {model_name}: {e}")
                    break

        logger.error(f"All Gemini model attempts failed. Last error: {last_error}. Utilizing safe fallback.")
        return cls._heuristic_fallback(text)

    @classmethod
    def _heuristic_fallback(cls, text: str) -> GeminiParsedIntent:
        """
        Safe local heuristic fallback when Gemini API is unreachable, quota-exhausted, or unconfigured.
        Strictly observes capability boundaries to prevent hallucinating stock actions.
        """
        import re
        from decimal import Decimal

        text_lower = text.lower().strip()

        # 1. Spoken Confirmation check
        if any(w in text_lower for w in ["confirm", "proceed", "aama confirm pannu", "confirm pannu", "sari pannu"]) or text_lower in ["aama", "yes", "sari", "ok", "confirm"]:
            return GeminiParsedIntent(
                intent="CONFIRMATION",
                is_confirmation=True,
                spoken_reply_english="Confirmed. Processing the transaction.",
                spoken_reply_tamil="Sari, confirm pannuren.",
            )

        # 2. Cancellation check
        if any(w in text_lower for w in ["cancel", "vendaam", "vendam", "stop", "cancel pannidu"]) or text_lower in ["no", "vendaam", "vendam", "cancel"]:
            return GeminiParsedIntent(
                intent="CANCELLATION",
                is_cancellation=True,
                spoken_reply_english="Cancelled. The pending transaction has been discarded.",
                spoken_reply_tamil="Transaction cancel pannittaen.",
            )

        # 3. DISCOUNT OR OFFER (Explicitly Unsupported Boundary)
        if any(w in text_lower for w in ["offer", "discount", "percent", "percentage", "%", "thallupadi", "coupon"]):
            pct_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|percentage)?", text_lower)
            pct = float(pct_m.group(1)) if pct_m else None
            prod = None
            for candidate in ["milk", "rice", "tomato", "thakkali", "biscuit", "atta", "oil", "dal", "ghee"]:
                if candidate in text_lower:
                    prod = candidate
                    break
            return GeminiParsedIntent(
                intent="DISCOUNT_OR_OFFER",
                is_supported=False,
                product_raw=prod,
                discount_percent=pct,
                unsupported_reason="Discount and promotional offer management is not currently supported in this application. No changes have been made to prices or inventory.",
                spoken_reply_english="Discount and offer management is not currently supported in this application.",
                spoken_reply_tamil="Discount alladhu offer management indha app-la ipodhikku illai.",
            )

        # 4. PRICE MODIFICATION (Explicitly Unsupported Boundary)
        if any(w in text_lower for w in ["change price", "set price", "update price", "vilai maathu", "price of", "new price", "change the price"]):
            return GeminiParsedIntent(
                intent="PRICE_MODIFICATION",
                is_supported=False,
                unsupported_reason="Price modification via voice is not supported. Please edit selling prices in the product catalog.",
                spoken_reply_english="Price modification via voice assistant is not currently supported.",
                spoken_reply_tamil="Voice assistant vazhiyaaga vilai maatra mudiyaadhu.",
            )

        # 5. Multi-turn Correction check (e.g. "Illa, 5 illa 3 packet", "change to 4")
        if (
            not any(p in text_lower for p in ["price", "vilai", "rate"])
            and any(w in text_lower for w in ["illa", "not ", "instead", "change to", "maathidu"])
            and re.search(r"\b\d+(?:\.\d+)?\b", text_lower)
        ):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", text_lower)
            qty = Decimal(nums[-1]) if nums else None
            unit_match = re.search(r"\b(packet|packets|kg|kgs|bag|bags|bottle|bottles|tin|tins|piece|pieces|litre|litres)\b", text_lower)
            unit_val = unit_match.group(1) if unit_match else None
            return GeminiParsedIntent(
                intent="CORRECTION",
                is_correction=True,
                quantity=float(qty) if qty is not None else None,
                unit=unit_val,
                spoken_reply_english=f"Quantity updated to {qty} {unit_val or ''}. Confirm when ready.",
                spoken_reply_tamil=f"Alavu {qty} {unit_val or ''}-a maathittaen. Confirm pannalaamaa?",
            )

        # 6. Record sale
        if any(w in text_lower for w in ["record sale", "vithuten", "sold", "sale pannu", "sale of"]):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", text_lower)
            qty = Decimal(nums[0]) if nums else None
            unit_match = re.search(r"\b(packet|packets|kg|kgs|bag|bags|bottle|bottles|tin|tins|piece|pieces|litre|litres)\b", text_lower)
            unit_val = unit_match.group(1) if unit_match else None
            prod = None
            for candidate in ["milk", "rice", "tomato", "thakkali", "biscuit", "atta", "oil", "dal", "sugar", "salt"]:
                if candidate in text_lower:
                    prod = candidate
                    break
            missing = []
            if qty is None:
                missing.append("quantity")
            if not prod:
                missing.append("product")

            return GeminiParsedIntent(
                intent="RECORD_SALE",
                product_raw=prod,
                product_normalized=prod.capitalize() if prod else None,
                quantity=float(qty) if qty is not None else None,
                unit=unit_val,
                missing_parameters=missing,
                spoken_reply_english=(
                    f"Proposing sale of {qty} {unit_val or ''} of {prod}. Please confirm."
                    if not missing else
                    f"How many {unit_val or 'units'} of {prod or 'the product'} would you like to record?"
                ),
                spoken_reply_tamil=(
                    f"{qty} {unit_val or ''} {prod} sale panna confirm pannunga."
                    if not missing else
                    f"{prod or 'Product'}-oda ethanai alavu sale panna vendum?"
                ),
            )

        # 7. Receive stock
        if any(w in text_lower for w in ["receive", "received", "vandhuruchu", "vandhiruchu", "stock receipt"]):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", text_lower)
            qty = Decimal(nums[0]) if nums else None
            unit_match = re.search(r"\b(packet|packets|kg|kgs|bag|bags|bottle|bottles|tin|tins|piece|pieces|litre|litres)\b", text_lower)
            unit_val = unit_match.group(1) if unit_match else None
            prod = None
            for candidate in ["biscuit", "milk", "rice", "tomato", "thakkali", "atta", "oil", "dal"]:
                if candidate in text_lower:
                    prod = candidate
                    break
            missing = []
            if qty is None:
                missing.append("quantity")
            if not prod:
                missing.append("product")

            return GeminiParsedIntent(
                intent="RECEIVE_STOCK",
                product_raw=prod,
                product_normalized=prod.capitalize() if prod else None,
                quantity=float(qty) if qty is not None else None,
                unit=unit_val,
                missing_parameters=missing,
                spoken_reply_english=(
                    f"Proposing stock receipt of {qty} {unit_val or ''} of {prod}. Please confirm."
                    if not missing else
                    f"How many {unit_val or 'units'} of {prod or 'the product'} did you receive?"
                ),
                spoken_reply_tamil=(
                    f"{qty} {unit_val or ''} {prod} stock receipt confirm pannunga."
                    if not missing else
                    f"{prod or 'Product'}-la ethanai alavu vandhadhu?"
                ),
            )

        # 8. Sales info
        if any(w in text_lower for w in ["sales", "innaiku sales", "sold today", "revenue", "turnover"]):
            return GeminiParsedIntent(
                intent="SALES_INFO",
                time_frame="today",
                spoken_reply_english="Fetching today's sales summary.",
                spoken_reply_tamil="Innaiku sales summary paakkuren.",
            )

        # 9. Expiry
        if any(w in text_lower for w in ["expire", "expiry", "expiring", "expired"]):
            time_f = "tomorrow" if "tomorrow" in text_lower or "naalaiku" in text_lower else "7_days"
            return GeminiParsedIntent(
                intent="CHECK_EXPIRY",
                time_frame=time_f,
                spoken_reply_english=f"Checking products expiring {time_f}.",
                spoken_reply_tamil=f"Expiring items list check panren.",
            )

        # 10. Low stock / Out of stock
        if any(w in text_lower for w in ["out of stock", "theendhu", "theenthurchu"]):
            return GeminiParsedIntent(
                intent="CHECK_OUT_OF_STOCK",
                spoken_reply_english="Checking out of stock products.",
                spoken_reply_tamil="Theendhu pona items check panren.",
            )
        if any(w in text_lower for w in ["low stock", "kammiya", "running low"]):
            return GeminiParsedIntent(
                intent="CHECK_LOW_STOCK",
                spoken_reply_english="Checking low stock items.",
                spoken_reply_tamil="Kammiya irukkura items check panren.",
            )

        # 11. Reorder / Budget
        if any(w in text_lower for w in ["reorder", "budget", "recommend", "vaanganum"]):
            budget_val = None
            b_match = re.search(r"\b(\d+(?:,\d+)?)\s*(?:rooba|rupee|rs|inr)?\s*budget\b", text_lower)
            if b_match:
                try:
                    budget_val = float(b_match.group(1).replace(",", ""))
                except Exception:
                    pass
            return GeminiParsedIntent(
                intent="AI_RECOMMENDATION",
                budget=budget_val,
                spoken_reply_english="Calculating smart purchase recommendations.",
                spoken_reply_tamil="Reorder panna vendiya items check panren.",
            )

        # 12. Explicit Stock Check Queries
        if any(w in text_lower for w in ["stock", "available", "left", "irukku", "evlo", "irukka", "how much", "how many", "quantity"]):
            prod = None
            for candidate in ["milk", "rice", "tomato", "thakkali", "biscuit", "atta", "oil", "dal", "sugar", "salt", "ghee", "bread"]:
                if candidate in text_lower:
                    prod = candidate
                    break
            return GeminiParsedIntent(
                intent="CHECK_STOCK",
                product_raw=prod or text,
                product_normalized=prod.capitalize() if prod else None,
                spoken_reply_english="Checking stock for the requested item.",
                spoken_reply_tamil="Stock check panren.",
            )

        # 13. Default Unknown Input (DO NOT default to CHECK_STOCK)
        return GeminiParsedIntent(
            intent="UNKNOWN",
            is_supported=False,
            spoken_reply_english="I couldn't identify that command. You can ask about stock, expiring products, sales, or record transactions.",
            spoken_reply_tamil="Enakku puriyavillai. Stock, sales, alladhu transactions patri ketkalaam.",
        )
