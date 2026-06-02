import structlog
from openai import AsyncOpenAI

from app.config import config

logger = structlog.get_logger()

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )
    return _client


async def transcribe_audio(file_path: str) -> tuple[str, float]:
    """
    Transcribe audio using OpenAI gpt-4o-transcribe (Russian / English).

    Returns (transcript_text, confidence).
    confidence is None when the API does not return it.
    """
    client = get_client()

    with open(file_path, "rb") as f:
        response = await client.audio.transcriptions.create(
            model=config.openai_stt_model,
            file=f,
            response_format="verbose_json",
        )

    text = response.text or ""
    # The API may return a confidence field; default to None so the caller
    # can distinguish "unknown" from "low" and trigger the Muxlisa fallback.
    confidence = getattr(response, "confidence", None)

    logger.info(
        "stt_openai_completed",
        model=config.openai_stt_model,
        text_length=len(text),
        confidence=confidence,
    )
    return text, confidence
