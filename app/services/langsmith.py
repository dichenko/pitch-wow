import os

import structlog

from app.config import config

logger = structlog.get_logger()


def setup_langsmith():
    """Configure LangSmith tracing if enabled."""
    if config.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = config.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = config.langsmith_project
        logger.info("langsmith_configured", project=config.langsmith_project)


def get_trace_metadata(state: dict, prompt_version: str = "") -> dict:
    return {
        "session_id": state.get("session_id", ""),
        "telegram_user_id": state.get("telegram_user_id", 0),
        "phase": state.get("phase", "unknown"),
        "personality_dev_level": state.get("personality_dev_level", ""),
        "prompt_version": prompt_version,
    }
