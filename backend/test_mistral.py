import httpx
from app.core.config import settings

url = "https://api.mistral.ai/v1/chat/completions"

payload = {
    "model": settings.MISTRAL_MODEL,
    "messages": [
        {
            "role": "user",
            "content": "Reply with: Inventra Mistral connection successful!"
        }
    ],
    "max_tokens": 60,
    "temperature": 0.2
}

headers = {
    "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
    "Content-Type": "application/json"
}

try:
    response = httpx.post(
        url,
        headers=headers,
        json=payload,
        timeout=60
    )
    response.raise_for_status()

    result = response.json()
    print("API connection: SUCCESS")
    print("Model:", result.get("model"))
    print("Mistral response:")
    print(result["choices"][0]["message"]["content"])

except httpx.HTTPStatusError as exc:
    print("API request failed. HTTP status:", exc.response.status_code)
    print("Mistral error details:", exc.response.text)

except Exception as exc:
    print("Connection error:", type(exc).__name__, str(exc))
