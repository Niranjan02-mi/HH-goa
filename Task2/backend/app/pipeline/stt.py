"""
Sarvam AI STT integration (Saaras v3).
Transcribes audio to Hindi text with retries and timeout.
"""

import base64
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.models import STTResponse
from app.utils.latency import timed_ms


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    reraise=True,
)
async def transcribe(audio_bytes: bytes) -> STTResponse:
    """
    Send audio to Sarvam Saaras v3 STT and return transcript.
    Audio should be WAV or WebM format.
    """
    with timed_ms() as timing:
        headers = {
            "api-subscription-key": settings.sarvam_api_key,
        }

        # The frontend records as webm, but we label it audio/webm to be safe.
        files = {
            "file": ("audio.wav", audio_bytes, "audio/wav")
        }

        # Use Unknown for automatic language detection
        data = {
            "language_code": "Unknown",
            "model": "saaras:v3"
        }

        async with httpx.AsyncClient(timeout=settings.stt_timeout) as client:
            response = await client.post(
                settings.sarvam_stt_url,
                files=files,
                data=data,
                headers=headers,
            )
            if response.status_code >= 400:
                print(f"STT Error Response: {response.text}")
            response.raise_for_status()
            res_data = response.json()

        transcript = res_data.get("transcript", "")
        # Safely extract detected language
        detected_lang = res_data.get("language_code", "Unknown")

    return STTResponse(
        transcript=transcript,
        language=detected_lang,
        latency_ms=timing["ms"],
    )
