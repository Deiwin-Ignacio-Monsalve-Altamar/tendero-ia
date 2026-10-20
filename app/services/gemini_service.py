import os
import time
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.utils.error_handlers import AppError, RateLimitError

class ExtractedItem(BaseModel):
    raw_name: str
    canonical_name: str
    quantity: int
    unit_price: Optional[float] = None
    subtotal: Optional[float] = None

class GeminiNLUResponse(BaseModel):
    intent: Literal["RECORD_SALE", "RECORD_EXPENSE", "CONFIRM", "CANCEL", "QUERY_REPORT", "UNKNOWN"]
    items: List[ExtractedItem] = Field(default_factory=list)
    total_amount: float = 0.0

class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-3.1-flash-lite"

    def extract_from_text(self, text: str, catalog_context: str) -> GeminiNLUResponse:
        system_prompt = (
            "You extract sales from a shopkeeper's message. Match existing products against "
            "the provided catalog. If the user mentions a price for an item, extract it in "
            "unit_price. If the item exists in the catalog and the user gives no price, use "
            "the catalog price. If it is a new item and no price is mentioned, set unit_price "
            "to null; the application will ask the shopkeeper for its price. Never invent a "
            "price. Return RECORD_SALE when products are mentioned, including new products. "
            "Si el usuario menciona un precio para un ítem, extráelo en unit_price. Si el ítem "
            "ya existe en el catálogo provisto y el usuario no dio precio, usa el precio del "
            "catálogo. Si es un ítem nuevo y no menciona precio, deja unit_price en null y "
            "solicita aclaración en la respuesta.\n\n"
            f"Shop catalog (COP):\n{catalog_context}"
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=GeminiNLUResponse,
            ),
        )
        return GeminiNLUResponse.model_validate_json(response.text)

    def extract_from_image(
        self, image_bytes: bytes, mime_type: str, catalog_context: str = ""
    ) -> GeminiNLUResponse:
        prompt = "Extract sale details from this receipt. Match items to the provided catalog."
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Use only prices explicitly visible on the receipt or in this business catalog. "
                    "Set unit_price and subtotal to null when unavailable.\n\n"
                    f"Business catalog (COP):\n{catalog_context}"
                ),
                response_mime_type="application/json",
                response_schema=GeminiNLUResponse,
            ),
        )
        return GeminiNLUResponse.model_validate_json(response.text)

    def extract_from_audio(
        self, audio_bytes: bytes, catalog_context: str, mime_type: str = "audio/ogg"
    ) -> GeminiNLUResponse:
        system_prompt = (
            "You extract sales from a shopkeeper's audio note. Understand the audio directly. "
            "Match existing products against the provided catalog. If the user mentions a "
            "price for an item, extract it in unit_price. If the item exists in the catalog "
            "and the user gives no price, use the catalog price. If it is a new item and no "
            "price is mentioned, set unit_price to null; the application will ask the "
            "shopkeeper for its price. Never invent a price. Return RECORD_SALE when products "
            "are mentioned, including new products. Si el usuario menciona un precio para un "
            "ítem, extráelo en unit_price. Si el ítem ya existe en el catálogo provisto y el "
            "usuario no dio precio, usa el precio del catálogo. Si es un ítem nuevo y no "
            "menciona precio, deja unit_price en null y solicita aclaración en la respuesta.\n\n"
            f"Shop catalog (COP):\n{catalog_context}"
        )
        contents = [types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=GeminiNLUResponse,
        )

        for attempt in range(2):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as exc:
                status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                try:
                    status = int(status)
                except (TypeError, ValueError):
                    status = None
                if status not in (429, 503) or attempt == 1:
                    if status == 429:
                        raise RateLimitError(details={"provider": "Gemini"}) from exc
                    if status == 503:
                        raise AppError(
                            "Gemini no está disponible temporalmente", 503, "GEMINI_UNAVAILABLE"
                        ) from exc
                    raise
                time.sleep(0.5)
        return GeminiNLUResponse.model_validate_json(response.text)
