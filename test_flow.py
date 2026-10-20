import requests
from pathlib import Path

BASE_URL = "http://localhost:5000/api/v1/demo"
PRODUCTS_URL = "http://localhost:5000/api/v1/products"
PHONE = "123456"

# Seed the tenant catalog so the text and audio flows can resolve its products.
catalog_response = requests.get(PRODUCTS_URL, params={"phone": PHONE})
catalog_response.raise_for_status()
known_products = {
    product["canonical_name"]
    for product in catalog_response.json()["data"]
}
for product_name, price in [
    ("Almuerzo Ejecutivo", 16000),
    ("Picada", 25000),
    ("Gaseosa", 3500),
]:
    if product_name not in known_products:
        created = requests.post(PRODUCTS_URL, json={
            "phone": PHONE,
            "name": product_name,
            "price": price,
        })
        created.raise_for_status()

# 1. Send order
print("--- Step 1: Sending order ---")
resp1 = requests.post(f"{BASE_URL}/simulate-text", json={
    "sender_phone": PHONE,
    "message_text": "Quiero un almuerzo ejecutivo, una picada y una gaseosa"
})
payload1 = resp1.json()
assert resp1.status_code == 200, payload1.get("error", payload1)
assert payload1.get("success") is True and "response" in payload1.get("data", {}), payload1
print(payload1["data"])

# 2. Confirm
print("\n--- Step 2: Confirming ---")
resp2 = requests.post(f"{BASE_URL}/simulate-text", json={
    "sender_phone": PHONE,
    "message_text": "Sí"
})
payload2 = resp2.json()
assert resp2.status_code == 200, payload2.get("error", payload2)
assert payload2.get("success") is True and "response" in payload2.get("data", {}), payload2
print(payload2["data"])

# 3. Check Caja
print("\n--- Step 3: Checking Caja ---")
resp3 = requests.get(f"{BASE_URL}/caja", params={"phone": "123456"})
payload3 = resp3.json()
assert resp3.status_code == 200, payload3.get("error", payload3)
assert payload3.get("success") is True and "transactions" in payload3.get("data", {}), payload3
print(payload3["data"])

def test_audio_flow():
    """POST an audio sample and check the demo endpoint response shape."""
    audio_path = Path(__file__).with_name("test_audio.wav")
    audio_bytes = audio_path.read_bytes() if audio_path.exists() else b"mock audio bytes"
    mime_type = "audio/wav" if audio_path.exists() else "audio/ogg"
    response = requests.post(
        f"{BASE_URL}/simulate-audio",
        data={"sender_phone": "123456"},
        files={"file": (audio_path.name if audio_path.exists() else "sample.ogg", audio_bytes, mime_type)},
    )
    payload = response.json()
    assert response.status_code == 200, payload.get("error", payload)
    assert payload.get("success") is True, payload
    assert isinstance(payload.get("data"), dict) and "reply" in payload["data"], payload
    return payload["data"]
