import httpx
import structlog

from app.config import config

logger = structlog.get_logger()


async def transcribe_audio(file_path: str) -> tuple[str, float]:
    """
    Transcribe audio via Muxlisa STT (Uzbek language).

    Returns (transcript_text, confidence).
    confidence is None when the API does not return it.
    """
    timeout_sec = config.muxlisa_stt_timeout_ms / 1000

    with open(file_path, "rb") as f:
        audio_bytes = f.read()

    headers = {
        "Authorization": f"Bearer {config.muxlisa_api_key}",
        "Accept": "application/json",
    }
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(
                f"{config.muxlisa_base_url}/stt",
                headers=headers,
                files=files,
            )

        if response.status_code != 200:
            logger.error(
                "stt_muxlisa_http_error",
                status=response.status_code,
                body=response.text[:300],
            )
            return "", None

        data = response.json()

        # Handle multiple possible response shapes from Muxlisa
        text = (
            data.get("text")
            or data.get("transcript")
            or data.get("result")
            or ""
        )
        confidence = data.get("confidence")

        logger.info(
            "stt_muxlisa_completed",
            text_length=len(text),
            confidence=confidence,
        )
        return text, confidence

    except httpx.TimeoutException:
        logger.error("stt_muxlisa_timeout", timeout_sec=timeout_sec)
        return "", None
    except Exception as e:
        logger.error("stt_muxlisa_exception", error=str(e))
        return "", None
