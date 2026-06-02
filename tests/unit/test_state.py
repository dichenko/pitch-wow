import pytest


def test_config_defaults():
    import os
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
    from app.config import Config
    cfg = Config()
    assert cfg.app_env == "development"
    assert cfg.log_level == "INFO"


def test_state_structure():
    from app.graph.state import PitchWowState
    state: PitchWowState = {
        "session_id": "test",
        "telegram_chat_id": 123,
        "telegram_user_id": 456,
        "messages": [],
        "current_stage": "opening",
        "phase": "unknown",
        "phase_confidence": 0.5,
        "personality_confidence": 0.5,
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
    assert state["phase"] == "unknown"


@pytest.mark.asyncio
async def test_first_message_has_required_markers():
    from app.graph.builder import wings_interviewer_node
    state = {
        "session_id": "",
        "telegram_chat_id": 1,
        "telegram_user_id": 1,
        "messages": [],
        "current_stage": "opening",
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
    result = await wings_interviewer_node(state)
    msg = result.get("pending_response", "")

    required = ["Бабур", "Беруни", "Навои", "Улугбек", "Амир"]
    for marker in required:
        assert marker in msg, f"Missing required marker: {marker}"

    forbidden = ["AiME", "AiWE", "AiPROF", "Авиценна", "Томирис", "Мадина"]
    for marker in forbidden:
        assert marker not in msg, f"Forbidden marker found: {marker}"


def test_ne_regex():
    import re
    NE_RE = re.compile(r"\b[Нн]е\s+", re.UNICODE)
    assert NE_RE.search("Не переживай")
    assert NE_RE.search("не торопись")
    assert not NE_RE.search("Всё получится")
