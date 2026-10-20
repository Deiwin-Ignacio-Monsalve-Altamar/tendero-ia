import math

from app.repositories.transaction_repository import TransactionRepository
from app.services.gemini_service import GeminiService
from app.services.product_service import ProductService
from app.utils.error_handlers import AppError

PENDING_CONFIRMATIONS = {}
PENDING_PRODUCT_PRICES = {}


class SaleService:
    @staticmethod
    def _resolve_price_clarification(sender_phone: str, text: str):
        pending = PENDING_PRODUCT_PRICES.get(sender_phone)
        if pending is None:
            return None

        digits = "".join(character for character in text if character.isdigit())
        if not digits or int(digits) <= 0:
            item = pending["items"][pending["item_index"]]
            return f"El producto {item.canonical_name} es nuevo. ¿A qué precio lo vendes para guardarlo?"

        price = float(int(digits))
        item = pending["items"][pending["item_index"]]
        item.unit_price = price
        item.subtotal = item.quantity * price
        product, action = ProductService.upsert_catalog_product(
            pending["business_id"], item.canonical_name, price, item.raw_name
        )
        if action == "created":
            pending["catalog_notes"].append(f"{product.canonical_name} se agregó al catálogo.")
        del PENDING_PRODUCT_PRICES[sender_phone]
        return SaleService._prepare_sale(
            sender_phone,
            pending["business_id"],
            pending["items"],
            pending["raw_input"],
            pending["catalog_notes"],
        )

    @staticmethod
    def _prepare_sale(sender_phone, business_id, items, raw_input, catalog_notes=None):
        catalog_notes = list(catalog_notes or [])
        for index, item in enumerate(items):
            product = ProductService.find_product(business_id, item.canonical_name)
            price = item.unit_price
            if price is None:
                if product is None:
                    PENDING_CONFIRMATIONS.pop(sender_phone, None)
                    PENDING_PRODUCT_PRICES[sender_phone] = {
                        "business_id": business_id,
                        "items": items,
                        "item_index": index,
                        "raw_input": raw_input,
                        "catalog_notes": catalog_notes,
                    }
                    return (
                        f"El producto {item.canonical_name} es nuevo. "
                        "¿A qué precio lo vendes para guardarlo?"
                    )
                price = product.price

            if not math.isfinite(price) or price < 0:
                raise AppError("El precio del producto no es válido", 400, "INVALID_PRICE")
            product, action = ProductService.upsert_catalog_product(
                business_id, item.canonical_name, price, item.raw_name
            )
            item.canonical_name = product.canonical_name
            item.unit_price = price
            item.subtotal = item.quantity * price
            if action == "created":
                catalog_notes.append(f"{product.canonical_name} se agregó al catálogo.")
            elif action == "updated":
                catalog_notes.append(f"Se actualizó el precio de {product.canonical_name} en el catálogo.")

        total_amount = sum(item.subtotal for item in items)
        PENDING_CONFIRMATIONS[sender_phone] = {
            "business_id": business_id,
            "items": items,
            "total_amount": total_amount,
            "raw_input": raw_input,
        }
        item_lines = "\n".join(
            f"• {item.quantity}x {item.canonical_name} — ${item.unit_price:,.0f} COP c/u "
            f"(${item.subtotal:,.0f} COP)"
            for item in items
        )
        notes = "\n".join(f"📦 {note}" for note in catalog_notes)
        if notes:
            notes = f"\n{notes}"
        return (
            f"🔍 *Revisa los datos antes de registrar:*\n{item_lines}\n"
            f"💵 *Total:* ${total_amount:,.0f} COP{notes}\n"
            "¿Es correcto? Responde *Sí* para confirmar o *Cancelar*."
        )

    @staticmethod
    def process_incoming_text(sender_phone: str, text: str):
        business = ProductService.get_or_create_business(sender_phone)
        pending_price_reply = SaleService._resolve_price_clarification(sender_phone, text)
        if pending_price_reply is not None:
            return pending_price_reply

        text_lower = text.lower().strip()
        if sender_phone in PENDING_CONFIRMATIONS:
            if text_lower in ["si", "sí", "dale", "ok", "confirmar", "listo"]:
                data = PENDING_CONFIRMATIONS.pop(sender_phone)
                TransactionRepository.create_confirmed_sale(
                    sender_phone,
                    data.get("business_id", business.id),
                    data["items"],
                    data["total_amount"],
                    data["raw_input"],
                )
                daily_total = TransactionRepository.get_daily_total(business.id)
                return f"✅ Venta registrada. Total acumulado hoy: ${daily_total:,.0f}"

            if text_lower in ["cancelar", "cancela", "no"]:
                PENDING_CONFIRMATIONS.pop(sender_phone)
                return "❌ Venta cancelada."

        products = ProductService.list_active_products(business.id)
        result = GeminiService().extract_from_text(
            text, ProductService.format_catalog(products)
        )
        if result.intent == "RECORD_SALE" and result.items:
            return SaleService._prepare_sale(sender_phone, business.id, result.items, text)
        return "No entendí la instrucción."

    @staticmethod
    def process_incoming_audio(sender_phone: str, audio_bytes: bytes, mime_type: str = "audio/ogg") -> dict:
        business = ProductService.get_or_create_business(sender_phone)
        products = ProductService.list_active_products(business.id)
        result = GeminiService().extract_from_audio(
            audio_bytes, ProductService.format_catalog(products), mime_type
        )
        if result.intent == "RECORD_SALE" and result.items:
            reply = SaleService._prepare_sale(
                sender_phone, business.id, result.items, "Audio note"
            )
            return {"reply": reply}
        return {"reply": "No logré identificar productos en el audio. ¿Podrías repetir el pedido, por favor?"}

    @staticmethod
    def process_extracted_result(sender_phone: str, result, raw_input: str):
        business = ProductService.get_or_create_business(sender_phone)
        if result.intent == "RECORD_SALE" and result.items:
            return SaleService._prepare_sale(sender_phone, business.id, result.items, raw_input)
        return "No identifiqué productos de venta en el comprobante."

