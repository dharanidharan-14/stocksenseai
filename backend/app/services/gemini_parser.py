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
Your job is to understand shopkeeper speech and text, which is frequently spoken in:
- Standard English
- Pure Tamil script (e.g., 'அரிசி இருப்பு எவ்வளவு உள்ளது?')
- Tanglish (Tamil spoken in English letters, e.g., 'Tomato stock la evlo irukku?', 'Bro, tomato stock kammiya irukku pola', 'Innaiku sales evlo?', 'Naalaiku expire aagura items enna?')
- Local Kirana & Bazaar slang with Hindi/Tamil blends (e.g., 'Bhai, 5 packet aata customer ku kudu, bill podu', 'Pathu kilo thakkali vandhuruchu')

Rules for intent parsing:
1. Intent Classification:
   - CHECK_STOCK: Checking quantity or availability of a specific product (e.g., 'Tomato stock la evlo irukku?', 'Do we have sugar?').
   - CHECK_LOW_STOCK: Checking which items are running low or need reordering (e.g., 'Enna items kammiya irukku?', 'Low stock items list pannu').
   - CHECK_OUT_OF_STOCK: Checking zero-stock items (e.g., 'Theendhu pona items enna?').
   - CHECK_EXPIRY: Asking about expiring batches or expired food (e.g., 'Naalaiku expire aagura items enna?', 'Which milk batch expires first?').
   - SALES_INFO: Inquiries about turnover, revenue, or items sold (e.g., 'Innaiku sales evlo?', 'How much did I sell today?', 'Top selling item enna?').
   - AI_RECOMMENDATION: Asking what to purchase or asking for budget purchasing advice (e.g., 'What should I reorder today?', '2000 rooba budget la enna vaanganum?').
   - RECEIVE_STOCK: Receiving new inventory, inbound shipments, or adding batches (e.g., '10 kilo tomato vandhiruchu, stock update pannu', 'Tomato-ku innum pathu kilo serthu vidu', 'We received 20 packets of milk').
   - RECORD_SALE: Cashier recording customer purchases/sales (e.g., '5 packet biscuit sale panniten', 'Sold 2 packets milk').
   - RECORD_DAMAGE: Reporting spoiled, rotten, or damaged stock (e.g., '2 packet milk spoil aayiduchu', 'Damage entry podu').
   - INVENTORY_CORRECTION: Correcting stock discrepancies (e.g., 'Stock count thappa irukku, 15 kg maathividu').
   - CONFIRMATION: Answering yes to a pending proposal (e.g., 'Aama', 'Yes', 'Confirm pannu', 'Sari', 'Proceed').
   - CANCELLATION: Answering no or aborting (e.g., 'Cancel pannidu', 'Vendaam', 'Stop', 'No').
   - CORRECTION: Modifying a previous request (e.g., 'Illa, 5 illa 3 packet', 'Actually 10 kg mattum').
   - UNKNOWN: Irrelevant or completely unintelligible input.

2. Entity Extraction:
   - Extract the raw product mentioned in 'product_raw' (e.g. 'thakkali', 'aata', 'paal', 'milk').
   - Extract normalized English canonical name in 'product_normalized' (e.g. 'Tomato', 'Wheat Flour', 'Milk').
   - Extract numeric quantity in 'quantity' (e.g. 5, 10, 2.5). Convert spoken words ('pathu' -> 10, 'rendu' -> 2, 'five' -> 5).
   - Extract unit in 'unit' (packet, kg, gram, litre, ml, piece, box, bottle).
   - Extract time references in 'time_frame' ('today', 'tomorrow', '7_days', 'expired', or dates).
   - Extract rupee budget if mentioned in 'budget' (e.g. '2000 rooba' -> 2000.0).

3. Spoken Responses:
   - Provide a concise spoken response in English ('spoken_reply_english').
   - Provide an equivalent natural, friendly response in Tanglish ('spoken_reply_tamil') suitable for speech synthesis.
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
        Safe local heuristic fallback when Gemini API is unreachable or unconfigured.
        Ensures the shopkeeper always receives a helpful response without a 500 error.
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

        # 3. Multi-turn Correction check (e.g. "Illa, 5 illa 3 packet", "change to 4")
        if any(w in text_lower for w in ["illa", "not ", "instead", "change", "maathidu"]) and re.search(r"\b\d+(?:\.\d+)?\b", text_lower):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", text_lower)
            qty = Decimal(nums[-1]) if nums else None
            unit_match = re.search(r"\b(packet|packets|kg|kgs|bag|bags|bottle|bottles|tin|tins|piece|pieces|litre|litres)\b", text_lower)
            unit_val = unit_match.group(1) if unit_match else None
            return GeminiParsedIntent(
                intent="CORRECTION",
                is_correction=True,
                quantity=qty,
                unit=unit_val,
                spoken_reply_english=f"Quantity updated to {qty} {unit_val or ''}. Confirm when ready.",
                spoken_reply_tamil=f"Alavu {qty} {unit_val or ''}-a maathittaen. Confirm pannalaamaa?",
            )

        # 4. Record sale (e.g. "record sale", "vithuten", "sale of 2 milk packets")
        if any(w in text_lower for w in ["record sale", "vithuten", "sold", "sale pannu", "sale of"]):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", text_lower)
            qty = Decimal(nums[0]) if nums else Decimal("1")
            unit_match = re.search(r"\b(packet|packets|kg|kgs|bag|bags|bottle|bottles|tin|tins|piece|pieces|litre|litres)\b", text_lower)
            unit_val = unit_match.group(1) if unit_match else None
            # Extract product keyword
            prod = None
            for candidate in ["milk", "rice", "tomato", "thakkali", "biscuit", "atta", "oil", "dal", "sugar", "salt"]:
                if candidate in text_lower:
                    prod = candidate
                    break
            return GeminiParsedIntent(
                intent="RECORD_SALE",
                product_raw=prod or text,
                product_normalized=prod,
                quantity=qty,
                unit=unit_val,
                spoken_reply_english=f"Proposing sale of {qty} {prod or 'items'}. Please confirm.",
                spoken_reply_tamil=f"{qty} {prod or 'items'} sale panna confirm pannunga.",
            )

        # 5. Receive stock (e.g. "received 10 biscuit", "vandhuruchu", "stock receipt")
        if any(w in text_lower for w in ["receive", "received", "vandhuruchu", "vandhiruchu", "stock receipt"]):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", text_lower)
            qty = Decimal(nums[0]) if nums else Decimal("1")
            unit_match = re.search(r"\b(packet|packets|kg|kgs|bag|bags|bottle|bottles|tin|tins|piece|pieces|litre|litres)\b", text_lower)
            unit_val = unit_match.group(1) if unit_match else None
            prod = None
            for candidate in ["biscuit", "milk", "rice", "tomato", "thakkali", "atta", "oil", "dal"]:
                if candidate in text_lower:
                    prod = candidate
                    break
            return GeminiParsedIntent(
                intent="RECEIVE_STOCK",
                product_raw=prod or text,
                product_normalized=prod,
                quantity=qty,
                unit=unit_val,
                spoken_reply_english=f"Proposing stock receipt of {qty} {prod or 'items'}. Please confirm.",
                spoken_reply_tamil=f"{qty} {prod or 'items'} stock receipt confirm pannunga.",
            )

        # 6. Sales info
        if any(w in text_lower for w in ["sales", "innaiku sales", "sold today", "revenue", "turnover"]):
            return GeminiParsedIntent(
                intent="SALES_INFO",
                time_frame="today",
                spoken_reply_english="Fetching today's sales summary.",
                spoken_reply_tamil="Innaiku sales summary paakkuren.",
            )

        # 7. Expiry
        if any(w in text_lower for w in ["expire", "expiry", "expiring", "expired"]):
            time_f = "tomorrow" if "tomorrow" in text_lower or "naalaiku" in text_lower else "7_days"
            return GeminiParsedIntent(
                intent="CHECK_EXPIRY",
                time_frame=time_f,
                spoken_reply_english=f"Checking products expiring {time_f}.",
                spoken_reply_tamil=f"Expiring items list check panren.",
            )

        # 8. Low stock / Out of stock
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

        # 9. Reorder / Budget
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

        # 10. Default stock check
        return GeminiParsedIntent(
            intent="CHECK_STOCK",
            product_raw=text,
            spoken_reply_english="Checking stock for the requested item.",
            spoken_reply_tamil="Stock check panren.",
        )
