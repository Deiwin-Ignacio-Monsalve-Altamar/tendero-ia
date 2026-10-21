import logging
import os
from io import BytesIO
from typing import Tuple

import requests

logger = logging.getLogger(__name__)
GRAPH_API_BASE = "https://graph.facebook.com/v20.0"
REQUEST_TIMEOUT_SECONDS = 30


class WhatsAppConfigurationError(RuntimeError):
    """Raised when an inbound Meta operation requires credentials that are absent."""


class WhatsAppService:
    @staticmethod
    def _credentials():
        token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        return token, phone_number_id

    @staticmethod
    def _simulate_local(operation: str, details: str) -> dict:
        logger.warning("MODO DEMO/LOCAL - WhatsApp %s simulado: %s", operation, details)
        return {"status": "SIMULATED_LOCAL"}

    @staticmethod
    def download_media(media_id: str) -> Tuple[bytes, str]:
        token, _ = WhatsAppService._credentials()
        if not token:
            logger.warning(
                "MODO DEMO/LOCAL - No se puede descargar el medio %s sin WHATSAPP_ACCESS_TOKEN",
                media_id,
            )
            raise WhatsAppConfigurationError("Falta WHATSAPP_ACCESS_TOKEN")

        headers = {"Authorization": f"Bearer {token}"}
        metadata_response = requests.get(
            f"{GRAPH_API_BASE}/{media_id}",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        media_url = metadata.get("url")
        if not media_url:
            raise ValueError("Meta no devolvió una URL de descarga para el medio")

        media_response = requests.get(
            media_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        media_response.raise_for_status()
        content_type = (
            media_response.headers.get("Content-Type")
            or metadata.get("mime_type")
            or "audio/ogg"
        )
        mime_type = content_type.split(";", 1)[0].strip() or "audio/ogg"
        return media_response.content, mime_type

    @staticmethod
    def send_text_message(to_phone: str, message: str) -> dict:
        token, phone_number_id = WhatsAppService._credentials()
        if not token or not phone_number_id:
            return WhatsAppService._simulate_local(
                "send_text_message", f"destinatario={to_phone}, mensaje={message}"
            )

        response = requests.post(
            f"{GRAPH_API_BASE}/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to_phone,
                "type": "text",
                "text": {"preview_url": False, "body": message},
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def send_document_message(to_phone: str, pdf_bytes: BytesIO, filename: str) -> dict:
        token, phone_number_id = WhatsAppService._credentials()
        if not token or not phone_number_id:
            return WhatsAppService._simulate_local(
                "send_document_message",
                f"destinatario={to_phone}, archivo={filename}, bytes={pdf_bytes.getbuffer().nbytes}",
            )

        pdf_bytes.seek(0)
        upload_response = requests.post(
            f"{GRAPH_API_BASE}/{phone_number_id}/media",
            headers={"Authorization": f"Bearer {token}"},
            data={"messaging_product": "whatsapp", "type": "application/pdf"},
            files={"file": (filename, pdf_bytes, "application/pdf")},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        upload_response.raise_for_status()
        media_id = upload_response.json().get("id")
        if not media_id:
            raise ValueError("Meta no devolvió el id del documento cargado")

        send_response = requests.post(
            f"{GRAPH_API_BASE}/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to_phone,
                "type": "document",
                "document": {"id": media_id, "filename": filename},
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        send_response.raise_for_status()
        return send_response.json()
