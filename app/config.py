import os
from dataclasses import dataclass, field


def _admin_tg_ids_from_env() -> list[int]:
    return [
        int(x.strip())
        for x in os.getenv("ADMIN_TG_IDS", "").split(",")
        if x.strip().isdigit()
    ]


@dataclass
class Config:
    app_env: str = os.getenv("APP_ENV", "development")
    admin_base_url: str = os.getenv("ADMIN_BASE_URL", "http://localhost:8000")

    postgres_db: str = os.getenv("POSTGRES_DB", "pitchwow")
    postgres_user: str = os.getenv("POSTGRES_USER", "pitchwow")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "pitchwow")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://pitchwow:pitchwow@localhost:5432/pitchwow",
    )

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Bot mode: "polling" (default, no public URL needed) or "webhook" (requires HTTPS URL)
    telegram_mode: str = os.getenv("TELEGRAM_MODE", "polling")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_webhook_secret: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    telegram_webhook_url: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    telegram_webhook_port: int = int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443"))

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_primary_model: str = os.getenv("ANTHROPIC_PRIMARY_MODEL", "claude-sonnet-4-6")
    anthropic_classifier_model: str = os.getenv("ANTHROPIC_CLASSIFIER_MODEL", "claude-haiku-4-5")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_stt_model: str = os.getenv("OPENAI_STT_MODEL", "gpt-4o-transcribe")

    # Muxlisa STT (Uzbek fallback)
    muxlisa_api_key: str = os.getenv("MUXLISA_API_KEY", "")
    muxlisa_base_url: str = os.getenv("MUXLISA_BASE_URL", "https://service.muxlisa.uz")
    muxlisa_stt_timeout_ms: int = int(os.getenv("MUXLISA_STT_TIMEOUT_MS", "60000"))
    muxlisa_tts_timeout_ms: int = int(os.getenv("MUXLISA_TTS_TIMEOUT_MS", "60000"))
    muxlisa_max_audio_size_mb: int = int(os.getenv("MUXLISA_MAX_AUDIO_SIZE_MB", "5"))
    muxlisa_max_audio_duration_sec: int = int(os.getenv("MUXLISA_MAX_AUDIO_DURATION_SEC", "60"))
    muxlisa_tts_max_chars: int = int(os.getenv("MUXLISA_TTS_MAX_CHARS", "1512"))
    muxlisa_tts_speaker: int = int(os.getenv("MUXLISA_TTS_SPEAKER", "0"))

    # STT fallback: OpenAI (ru/en) → Muxlisa (uz) when confidence is below threshold
    stt_fallback_confidence_threshold: float = float(
        os.getenv("STT_FALLBACK_CONFIDENCE_THRESHOLD", "0.7")
    )
    stt_max_retries: int = int(os.getenv("STT_MAX_RETRIES", "2"))

    yandex_folder_id: str = os.getenv("YANDEX_FOLDER_ID", "")
    yandex_api_key: str = os.getenv("YANDEX_API_KEY", "")
    yandex_tts_voice: str = os.getenv("YANDEX_TTS_VOICE", "marina")
    yandex_tts_role: str = os.getenv("YANDEX_TTS_ROLE", "friendly")
    yandex_tts_speed: float = float(os.getenv("YANDEX_TTS_SPEED", "1.05"))
    yandex_tts_format: str = os.getenv("YANDEX_TTS_FORMAT", "oggopus")

    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "pitchwow-dev")

    # Admin panel auth: access is controlled by Telegram user IDs.
    # Admin sends /admin to the bot → bot generates a signed one-time login link.
    admin_tg_ids: list[int] = field(default_factory=_admin_tg_ids_from_env)
    admin_session_secret: str = os.getenv("ADMIN_SESSION_SECRET", "pitchwow-dev-secret")
    admin_session_max_age_hours: int = int(os.getenv("ADMIN_SESSION_MAX_AGE_HOURS", "3"))

    sentry_dsn: str = os.getenv("SENTRY_DSN", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
