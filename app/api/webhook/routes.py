import logging
import os

from flask import Blueprint, abort, jsonify, request

from app.services.report_service import ReportService
from app.services.sale_service import SaleService
from app.services.whatsapp_service import (
    WhatsAppConfigurationError,
    WhatsAppService,
)

logger = logging.getLogger(__name__)
webhook_bp = Blueprint("webhook_bp", __name__)


def _get_incoming_message(payload):
    if not isinstance(payload, dict):
        return None
    entries = payload.get("entry")
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        return None
    changes = entries[0].get("changes")
    if not isinstance(changes, list) or not changes or not isinstance(changes[0], dict):
        return None
    value = changes[0].get("value")
    if not isinstance(value, dict):
        return None
    messages = value.get("messages")
    if not isinstance(messages, list) or not messages or not isinstance(messages[0], dict):
        return None
    return messages[0]


def _reply_text(result) -> str:
    if isinstance(result, dict):
        return str(result.get("reply", result.get("response", "Mensaje procesado.")))
    return str(result)


@webhook_bp.route("", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    verify_token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")
    expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "tendero_token_secreto_2026")

    if mode == "subscribe" and verify_token == expected_token:
        return challenge, 200, {"Content-Type": "text/plain; charset=utf-8"}
    abort(403)


@webhook_bp.route("", methods=["POST"])
def receive_webhook():
    payload = request.get_json(silent=True)
    message = _get_incoming_message(payload)
    if message is None:
        return jsonify({"status": "EVENT_RECEIVED"}), 200

    sender_phone = message.get("from")
    if not sender_phone:
        return jsonify({"status": "EVENT_RECEIVED"}), 200

    message_type = message.get("type")
    if message_type == "text":
        text_data = message.get("text")
        text_body = text_data.get("body") if isinstance(text_data, dict) else None
        if not isinstance(text_body, str) or not text_body.strip():
            return jsonify({"status": "EVENT_RECEIVED"}), 200

        normalized_text = text_body.strip().lower()
        if any(term in normalized_text for term in ("reporte", "pdf", "balance", "ventas de hoy")):
            pdf_buffer = ReportService.generate_sales_pdf(sender_phone)
            filename = f"reporte_ventas_{sender_phone}.pdf"
            WhatsAppService.send_document_message(sender_phone, pdf_buffer, filename)
            reply_text = "Te compartí el reporte de ventas en PDF."
        else:
            reply_text = _reply_text(
                SaleService.process_incoming_text(sender_phone, text_body.strip())
            )
            WhatsAppService.send_text_message(sender_phone, reply_text)
        return jsonify({"status": "PROCESSED", "reply": reply_text}), 200

    if message_type == "audio":
        audio_data = message.get("audio")
        media_id = audio_data.get("id") if isinstance(audio_data, dict) else None
        if not media_id:
            return jsonify({"status": "EVENT_RECEIVED"}), 200
        try:
            audio_bytes, mime_type = WhatsAppService.download_media(media_id)
        except WhatsAppConfigurationError:
            reply_text = (
                "Recibí tu nota de voz. El modo demo/local no puede descargar el audio "
                "sin las credenciales de WhatsApp configuradas."
            )
            WhatsAppService.send_text_message(sender_phone, reply_text)
            return jsonify({"status": "PROCESSED", "reply": reply_text}), 200

        reply_text = _reply_text(
            SaleService.process_incoming_audio(sender_phone, audio_bytes, mime_type)
        )
        WhatsAppService.send_text_message(sender_phone, reply_text)
        return jsonify({"status": "PROCESSED", "reply": reply_text}), 200

    return jsonify({"status": "EVENT_RECEIVED"}), 200
