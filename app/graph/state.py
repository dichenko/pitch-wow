from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict

Phase = Literal["unknown", "Защита", "Кризис", "Крылья"]
PersonalityLevel = Literal["личность", "бизнес", "синергия"]
Outcome = Literal["completed", "short-session", "crisis-walk-away"]
QuestionClass = Literal["A1", "A2", "A3", "B1", "B2"]


class Message(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str
    ts: str
    source: Literal["text", "voice", "admin", "system"]
    langsmith_run_id: str | None


class PitchWowState(TypedDict, total=False):
    session_id: str
    telegram_chat_id: int
    telegram_user_id: int
    messages: list[Message]
    current_stage: str
    current_substage: str | None
    phase: Phase
    phase_confidence: float
    phase_calibrated_at: str | None
    personality_dev_level: PersonalityLevel | None
    personality_confidence: float
    a3_depth: int
    last_question_class: QuestionClass | None
    repeated_question_count: int
    macro_pattern_count: int
    live_observations: list[str]
    direct_quotes: list[str]
    signals_for_cartographer: list[str]
    natural_features: list[dict[str, Any]]
    investor_situation: Literal["реальная-в-работе", "гипотетическая", "отсутствует"]
    target_investor_hint: Literal["VC", "стратег", "ангел", "акселератор"] | None
    cross_sell_readiness: Literal["ready", "conditional", "not-ready"]
    next_node_hypothesis: Literal["Беруни", "Навои", "Улугбек", "none"]
    pending_response: str | None
    validated_response: str | None
    guardrail_retries: int
    guardrail_incidents: list[dict[str, Any]]
    artifacts: dict[str, Any]
    outcome: Outcome | None
    # Internal fields
    _system_prompt: str
    _prompt_version: str
    _llm_usage: dict[str, Any]
    _classifier_result: dict[str, Any]
