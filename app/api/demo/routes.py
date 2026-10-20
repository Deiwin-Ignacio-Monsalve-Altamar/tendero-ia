from flask import Blueprint, jsonify, request

from app.repositories.transaction_repository import TransactionRepository
from app.services.gemini_service import GeminiService
from app.services.product_service import ProductService
from app.services.sale_service import SaleService
from app.utils.error_handlers import AppError

demo_bp = Blueprint("demo_bp", __name__)


@demo_bp.route("/simulate-text", methods=["POST"])
def simulate_text():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError(
            "sender_phone y message_text requeridos", 400, "INVALID_PAYLOAD"
        )
    sender_phone = data.get("sender_phone")
    text = data.get("message_text") or data.get("text")
    if not isinstance(sender_phone, str) or not sender_phone.strip() or not isinstance(text, str) or not text.strip():
        raise AppError(
            "sender_phone y message_text requeridos", 400, "INVALID_PAYLOAD"
        )

    response = SaleService.process_incoming_text(sender_phone.strip(), text.strip())
    return jsonify({"success": True, "data": {"response": response}}), 200


@demo_bp.route("/simulate-image", methods=["POST"])
def simulate_image():
    phone = request.form.get("sender_phone")
    file = request.files.get("file")
    if not phone:
        raise AppError("sender_phone requerido", 400, "INVALID_PAYLOAD")
    if not file:
        raise AppError("Archivo de imagen requerido", 400, "MISSING_IMAGE_FILE")
    business = ProductService.get_or_create_business(phone)
    catalog_context = ProductService.format_catalog(
        ProductService.list_active_products(business.id)
    )
    result = GeminiService().extract_from_image(
        file.read(), file.content_type or "image/jpeg", catalog_context
    )
    reply = SaleService.process_extracted_result(phone, result, "Image upload")
    return jsonify({"success": True, "data": {"reply": reply}}), 200


@demo_bp.route("/simulate-audio", methods=["POST"])
def simulate_audio():
    phone = request.form.get("sender_phone") or request.args.get("sender_phone", "demo_user")
    file = request.files.get("file") or request.files.get("audio")
    if not file:
        raise AppError("Archivo de audio requerido", 400, "MISSING_AUDIO_FILE")

    response = SaleService.process_incoming_audio(
        phone, file.read(), file.content_type or "audio/ogg"
    )
    return jsonify({"success": True, "data": response}), 200


@demo_bp.route("/caja", methods=["GET"])
def get_caja():
    phone = request.args.get("phone")
    if not phone:
        raise AppError("phone requerido", 400, "INVALID_PAYLOAD")
    business = ProductService.get_or_create_business(phone)
    sales = TransactionRepository.get_confirmed_sales(business.id)
    data = {
        "total": TransactionRepository.get_confirmed_total(business.id),
        "transactions": [sale.to_dict() for sale in sales],
    }
    return jsonify({"success": True, "data": data}), 200
