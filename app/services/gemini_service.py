import os
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class ExtractedItem(BaseModel):
    product_name: str = Field(description="Name of the restaurant product (e.g., Almuerzo Ejecutivo, Picada, Gaseosa)")
    quantity: int = Field(description="Quantity sold", default=1)
    unit_price: float = Field(description="Unit price of the item in COP")

class SaleExtractionResult(BaseModel):
    is_sale_intent: bool = Field(description="True if the input describes a completed or requested sale transaction")
    items: List[ExtractedItem] = Field(default_factory=list, description="List of items extracted from the message or image")
    total_amount: float = Field(description="Total calculated sum of the items in COP", default=0.0)
    summary_text: str = Field(description="Friendly summary message to present to the merchant for verification")

RESTAURANT_MENU_CONTEXT = """
Standard Menu Prices (Restaurant):
- Almuerzo Ejecutivo: $16.000 COP
- Picada: $25.000 COP
- Gaseosa: $3.500 COP

Instructions:
Match user text or receipt images against these menu products and prices when available. 
If prices are explicitly mentioned or differ, use the explicit amount.
Calculate subtotals and the grand total accurately.
"""

class GeminiService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def process