import contextlib
import os
import tempfile

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from itsdangerous import URLSafeTimedSerializer

from app.config import config as app_config
from app.graph.builder import compile_graph
from app.graph.state import PitchWowState
from app.services import audio as audio_svc
from app.services import stt_muxlisa, stt_openai

router = Router()
logger = structlog.get_logger()

_graph = compile_graph()


def make_state(chat_id: int, user_id: int, messages: list | None = None) -> PitchWowState:
    return {
        "session_id": "",
        "telegram_chat_id": chat_id,
        "telegram_user_id": user_id,
        "messages": messages or [],
        "current_stage": "opening" if not messages else "calibration",
        "phase": "unknown",
        "phase_confidence": 0.0,
        "personality_confidence": 0.0,
        "a3_depth": 0,
        "repeated_question_count": 0,
        "macro_pattern_count": 0,
        "live_observations": [],
        "direct_quotes": [],
        "signals_for_cartographer": [],
        "natural_features": [],
        "investor_situation": "отсутствует",
        "cross_sell_readiness": "not-ready",
        "next_node_hypothesis": "none",
        "guardrail_retries": 0,
        "guardrail_incidents": [],
        "artifacts": {},
    }


def thread_id(chat_id: int, session_id: str = "default") -> dict[str, str]:
    return {"configurable": {"thread_id": f"telegram:{chat_id}:session:{session_id}"}}


@router.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id if message.from_user else 0
    state = make_state(message.chat.id, uid)
    config = thread_id(message.chat.id)

    result = await _graph.ainvoke(state, config)
    response_text = result.get("validated_response") or result.get("pending_response") or "Привет!"
    await message.answer(response_text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Pitch Wow — ИИ-коуч по распаковке продукта.\n\n"
        "/start — начать сессию\n"
        "/reset — сбросить сессию\n"
        "/voice_on — голосовые ответы\n"
        "/voice_off — только текст\n"
        "/status — текущий этап\n"
        "/help — эта справка"
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message):
    await message.answer("Сессия сброшена. Напиши /start для новой распаковки.")


@router.message(Command("voice_on"))
async def cmd_voice_on(message: Message):
    await message.answer("Голосовые ответы включены.")


@router.message(Command("voice_off"))
async def cmd_voice_off(message: Message):
    await message.answer("Голосовые ответы выключены. Буду отвечать текстом.")


@router.message(Command("status"))
async def cmd_status(message: Message):
    await message.answer("Сессия активна. Продолжай рассказывать.")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Generate a one-time admin login link if the sender is in ADMIN_TG_IDS."""
    uid = message.from_user.id if message.from_user else 0

    if uid not in app_config.admin_tg_ids:
        await message.answer("Доступ запрещён.")
        return

    app_config.admin_session_max_age_hours * 3600
    signer = URLSafeTimedSerializer(app_config.admin_session_secret)
    token = signer.dumps({"telegram_user_id": uid})
    login_url = f"{app_config.admin_base_url}/admin/login/token?token={token}"

    await message.answer(
        f"Ссылка для входа в админ-панель (действительна "
        f"{app_config.admin_session_max_age_hours} ч):\n{login_url}",
        disable_web_page_preview=True,
    )


# ── Voice message STT ───────────────────────────────────────────────────────

async def _transcribe_voice(bot, file_id: str) -> tuple[str, str]:
    """
    Download Telegram voice → ffmpeg → OpenAI STT → (fallback) Muxlisa.
    Returns (transcribed_text, provider) where provider is "openai" or "muxlisa".
    Returns ("", "") on total failure.
    """
    tmp_dir = tempfile.mkdtemp(prefix="pitchwow_stt_")
    raw_path = os.path.join(tmp_dir, "voice.ogg")
    wav_path = None

    try:
        # 1. Download from Telegram
        tg_file = await bot.get_file(file_id)
        await bot.download_file(tg_file.file_path, raw_path)

        # 2. Convert to 16 kHz mono WAV via ffmpeg
        wav_path = await audio_svc.prepare_audio(raw_path)

        # 3. Primary: OpenAI (Russian / English)
        text, confidence = await stt_openai.transcribe_audio(wav_path)

        threshold = app_config.stt_fallback_confidence_threshold
        needs_fallback = (
            not text
            or confidence is None
            or confidence < threshold
        )

        # 4. Fallback: Muxlisa (Uzbek) — when OpenAI could not recognise the language
        if needs_fallback and app_config.muxlisa_api_key:
            logger.info(
                "stt_fallback_to_muxlisa",
                openai_text_len=len(text),
                openai_confidence=confidence,
                threshold=threshold,
            )
            text, confidence = await stt_muxlisa.transcribe_audio(wav_path)
            return text.strip(), "muxlisa"

        return text.strip(), "openai"

    except Exception as e:
        logger.error("voice_transcription_failed", error=str(e))
        return "", ""

    finally:
        # Clean up temp files
        for path in (raw_path, wav_path):
            if path and os.path.exists(path):
                with contextlib.suppress(OSError):
                    os.remove(path)
        with contextlib.suppress(OSError):
            os.rmdir(tmp_dir)


@router.message(F.voice)
async def handle_voice(message: Message):
    """Receive a voice message, transcribe it, then run through the LangGraph pipeline."""
    if not message.voice:
        return

    uid = message.from_user.id if message.from_user else 0
    msg_ts = message.date.isoformat() if message.date else ""

    await message.answer("Распознаю...")

    text, provider = await _transcribe_voice(message.bot, message.voice.file_id)

    if not text:
        await message.answer(
            "Извини, не удалось распознать аудио. Попробуй ещё раз или напиши текстом."
        )
        return

    logger.info("voice_transcribed", provider=provider, text=text[:100])

    # Feed the transcribed text through the same pipeline as text messages
    state = make_state(message.chat.id, uid, [{
        "role": "user",
        "content": text,
        "ts": msg_ts,
        "source": "voice",
        "langsmith_run_id": None,
    }])

    graph_config = thread_id(message.chat.id)
    result = await _graph.ainvoke(state, graph_config)
    response_text = result.get("validated_response") or result.get("pending_response") or "Принято."
    await message.answer(response_text)


@router.message()
async def handle_text(message: Message):
    if not message.text:
        return

    uid = message.from_user.id if message.from_user else 0
    msg_ts = message.date.isoformat() if message.date else ""

    state = make_state(message.chat.id, uid, [{
        "role": "user",
        "content": message.text,
        "ts": msg_ts,
        "source": "text",
        "langsmith_run_id": None,
    }])

    config = thread_id(message.chat.id)
    result = await _graph.ainvoke(state, config)
    response_text = result.get("validated_response") or result.get("pending_response") or "Принято."
    await message.answer(response_text)
