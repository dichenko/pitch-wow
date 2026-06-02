from app.graph.state import PitchWowState


def detect_repeated_question(messages: list, current_user_message: str) -> bool:
    """
    Detect if the user is repeating the same question or pattern.
    Returns True if semantic repeat detected in last 3 messages.
    """
    user_msgs = [m for m in messages[-6:] if m["role"] == "user"]
    if len(user_msgs) < 2:
        return False

    # Simple heuristic: check for common question words
    q_words = {"что", "как", "почему", "зачем", "кто", "когда", "где"}
    prev_q = set()
    for msg in user_msgs[:-1]:
        words = set(msg["content"].lower().split())
        if words & q_words:
            prev_q.add(" ".join(sorted(words & q_words)))

    current_words = set(current_user_message.lower().split())
    current_q = " ".join(sorted(current_words & q_words))

    return current_q in prev_q and len(current_q) > 0


def detect_macro_pattern(messages: list) -> bool:
    """
    Detect if user uses macro-level patterns (markets, trends, stats)
    instead of personal/specific answers.
    """
    if len(messages) < 3:
        return False

    macro_keywords = {
        "рынок", "тренд", "тренды", "статистика", "волна", "волны",
        "индустрия", "отрасль", "сегмент", "ниша", "экономика",
        "market", "trend", "industry", "statistics",
    }

    user_msgs = [m for m in messages[-4:] if m["role"] == "user"]
    count = sum(
        1 for msg in user_msgs
        if any(kw in msg["content"].lower() for kw in macro_keywords)
    )
    return count >= 2


def compute_calibration(state: PitchWowState) -> PitchWowState:
    """
    Update phase calibration based on detected signals.
    Follows methodology rules:
    - Crisis has highest priority
    - Defense after 2 semantic repeats
    - Wings when readiness signals detected
    - personality_dev_level is background hypothesis
    """
    messages = state.get("messages", [])
    user_msgs = [m for m in messages if m["role"] == "user"]
    msg_count = len(user_msgs)

    # Crisis already set by classifier — highest priority, don't override
    if state.get("phase") == "Кризис":
        return state

    # Defense detection: repeated questions/arguments
    if msg_count >= 2:
        last_user = user_msgs[-1]["content"]
        if detect_repeated_question(messages, last_user):
            state["repeated_question_count"] = state.get("repeated_question_count", 0) + 1
            if state["repeated_question_count"] >= 2:
                state["phase"] = "Защита"
                state["phase_confidence"] = 0.8
                return state

    # Macro pattern detection for mirror-and-bid
    if detect_macro_pattern(messages):
        state["macro_pattern_count"] = state.get("macro_pattern_count", 0) + 1

    # After 3-5 user messages, if phase still unknown, default to Wings
    if msg_count >= 3 and state.get("phase") == "unknown":
        state["phase"] = "Крылья"
        state["phase_confidence"] = 0.4
        state["phase_calibrated_at"] = "auto"

    return state


def generate_mirror_and_bid(state: PitchWowState) -> str | None:
    """
    Generate mirror-and-bid response if macro pattern detected.
    Returns bid text or None.
    """
    if state.get("macro_pattern_count", 0) < 2:
        return None

    patent = (
        "Замечу паттерн: на прошлые вопросы ты отвечаешь рынком, трендами, статистикой — "
        "личный слой пока в тени. "
        "Моя гипотеза: твоя сила — системное мышление и чувство волн. "
        "Подтверди или поправь одним словом: это про тебя?"
    )
    return patent
