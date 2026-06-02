import httpx
import structlog

from app.config import config

logger = structlog.get_logger()

TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"


async def synthesize_speech(text: str) -> bytes | None:
    """
    Synthesize speech using Yandex SpeechKit (voice: marina).
    Returns OggOpus audio bytes or None on failure.
    """
    headers = {
        "Authorization": f"Api-Key {config.yandex_api_key}",
    }

    params = {
        "text": text,
        "voice": config.yandex_tts_voice,
        "emotion": config.yandex_tts_role,
        "speed": str(config.yandex_tts_speed),
        "format": config.yandex_tts_format,
        "folderId": config.yandex_folder_id,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(TTS_URL, headers=headers, data=params)
            if response.status_code == 200:
                logger.info("tts_synthesis_completed", text_length=len(text))
                return response.content
            else:
                logger.error("tts_error", status=response.status_code, body=response.text[:200])
                return None
    except Exception as e:
        logger.error("tts_exception", error=str(e))
        return None
