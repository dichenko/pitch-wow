import re
from typing import Any

import structlog
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph

from app.config import config
from app.graph.prompts.registry import load_active_prompt
from app.graph.state import PitchWowState
from app.services.anthropic_client import call_claude
from app.services.langsmith import setup_langsmith

setup_langsmith()
logger = structlog.get_logger()

NE_RE = re.compile(r"\b[Нн]е\s+", re.UNICODE)
FORBIDDEN_PERSONAS_RE = re.compile(r"(Авиценн[а-я]*|Томирис|Мадин[а-я]*)", re.IGNORECASE)
FIRST_MESSAGE_FORBIDDEN_RE = re.compile(r"(AiPROF|AiME|AiWE)", re.IGNORECASE)

MAX_GUARDRAIL_RETRIES = 2


async def normalize_turn(state: PitchWowState) -> PitchWowState:
    return state


async def load_runtime_settings(state: PitchWowState) -> PitchWowState:
    system_prompt = await load_active_prompt("babur.system")
    if system_prompt:
        state["_system_prompt"] = system_prompt[0]
        state["_prompt_version"] = system_prompt[1]
    return state


async def classify_incoming(state: PitchWowState) -> PitchWowState:
    classifier_prompt = await load_active_prompt("classifier.incoming_signals")
    if not classifier_prompt or not state.get("messages"):
        return state

    recent = state["messages"][-6:]
    current = state["messages"][-1] if state["messages"] else None
    if not current or current["role"] != "user":
        return state

    formatted_prompt = classifier_prompt[0].replace(
        "{{recent_messages}}",
        "\n".join(f"[{m['role']}]: {m['content']}" for m in recent[:-1]),
    ).replace("{{current_user_message}}", current["content"])

    try:
        response, _, _ = await call_claude(
            system_prompt=formatted_prompt,
            messages=[{"role": "user", "content": "Classify."}],
            model=config.anthropic_classifier_model,
            temperature=0.1,
            max_tokens=512,
        )

        import json
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            result = json.loads(json_match.group(0)) if json_match else {}

        state["_classifier_result"] = result

        if result.get("crisis_signal") and not result.get("defense_signal"):
            state["phase"] = "Кризис"
            state["phase_confidence"] = 0.8
        elif result.get("defense_signal"):
            state["phase"] = "Защита"
            state["phase_confidence"] = 0.7
        elif result.get("wings_signal"):
            state["phase"] = "Крылья"
            state["phase_confidence"] = 0.6

        if result.get("personality_dev_level_hint"):
            state["personality_dev_level"] = result["personality_dev_level_hint"]
            state["personality_confidence"] = 0.5

        if result.get("macro_pattern_signal"):
            state["macro_pattern_count"] = state.get("macro_pattern_count", 0) + 1

        if result.get("investor_situation"):
            state["investor_situation"] = result["investor_situation"]

    except Exception as e:
        logger.warning(
            "classifier_failed",
            error_type=type(e).__name__,
            error=str(e),
            model=config.anthropic_classifier_model,
        )

    return state


async def update_calibration(state: PitchWowState) -> PitchWowState:
    from app.graph.nodes.calibration import compute_calibration
    return compute_calibration(state)


def route_by_phase(state: PitchWowState) -> str:
    if state.get("phase") == "Кризис":
        return "crisis_node"
    if state.get("phase") == "Защита":
        return "defense_node"
    return "wings_interviewer_node"


async def crisis_node(state: PitchWowState) -> PitchWowState:
    state["pending_response"] = (
        "Слышу тебя. Сейчас важно побыть с живыми людьми. "
        "К Продукту можно вернуться позже, когда будет легче."
    )
    state["outcome"] = "crisis-walk-away"
    state["phase"] = "Кризис"
    return state


async def defense_node(state: PitchWowState) -> PitchWowState:
    state["pending_response"] = (
        "Вижу, сейчас лучше сохранить рамку. Оставлю тебе вопрос на подумать: "
        "какая стратегия даст твоему проекту большую капитализацию? "
        "Возвращайся, когда захочешь продолжить."
    )
    state["outcome"] = "short-session"
    state["phase"] = "Защита"
    return state


async def wings_interviewer_node(state: PitchWowState) -> PitchWowState:
    system_prompt = state.get("_system_prompt", "")
    if not system_prompt:
        try:
            system_prompt_result = await load_active_prompt("babur.system")
            if system_prompt_result:
                system_prompt = system_prompt_result[0]
        except Exception as e:
            logger.warning("system_prompt_load_failed", error_type=type(e).__name__, error=str(e))

    messages = state.get("messages", [])

    if not messages:
        state["pending_response"] = (
            "Я Бабур, ИИ-ассистент Pitch Wow по распаковке. "
            "Pitch Wow бесплатен — ты уходишь отсюда с картой природных особенностей "
            "и лендингом, который можно показывать. "
            "Дальше в холдинге soft-retail.ai, где мудрый голос — Амир, "
            "есть три узла: Беруни делает Insta-аудит SMM, Навои — контент-завод, "
            "Улугбек — аналитику и A2A. Каждый сам шлёт ссылку на оплату своего сервиса. "
            "Польза прямо сейчас — задача этой встречи. "
            "Решение про следующий шаг — твоё, и оно может быть любым. "
            "Расскажи в одном предложении: что ты делаешь?"
        )
        return state

    # Mirror-and-bid: if 2+ macro patterns detected, use template
    from app.graph.nodes.calibration import generate_mirror_and_bid
    mirror_bid = generate_mirror_and_bid(state)
    if mirror_bid:
        state["pending_response"] = mirror_bid
        return state

    try:
        response, input_tokens, output_tokens = await call_claude(
            system_prompt=system_prompt,
            messages=[{
                "role": m["role"],
                "content": m["content"],
            } for m in messages[-10:]],
            temperature=0.7,
            max_tokens=1024,
        )
        state["pending_response"] = response
        state["_llm_usage"] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": config.anthropic_primary_model,
            "prompt_version": state.get("_prompt_version", ""),
        }
    except Exception as e:
        logger.error(
            "wings_interviewer_failed",
            error_type=type(e).__name__,
            error=str(e),
            model=config.anthropic_primary_model,
        )
        state["pending_response"] = "Извини, произошла ошибка. Давай попробуем ещё раз."

    return state


async def guardrails_subgraph(state: PitchWowState) -> PitchWowState:
    draft = state.get("pending_response", "") or ""
    retries = state.get("guardrail_retries", 0)
    incidents = state.get("guardrail_incidents", [])

    # Check 1: "ne" particle
    if NE_RE.search(draft):
        ne_rewriter = await load_active_prompt("rewriter.no_ne_particle")
        if ne_rewriter and retries < MAX_GUARDRAIL_RETRIES:
            try:
                formatted = ne_rewriter[0].replace("{{draft_response}}", draft)
                rewritten, _, _ = await call_claude(
                    system_prompt=formatted,
                    messages=[{"role": "user", "content": "Rewrite."}],
                    temperature=0.1,
                    max_tokens=1024,
                )
                draft = rewritten.strip()
                retries += 1
            except Exception as e:
                logger.warning(
                    "guardrail_rewrite_failed",
                    rule="ne_particle",
                    error_type=type(e).__name__,
                    error=str(e),
                )
                incidents.append({"reason": "ne_particle", "original": draft[:200]})

    # Check 2-3: scope check
    if FORBIDDEN_PERSONAS_RE.search(draft) or (
        not state.get("messages") and FIRST_MESSAGE_FORBIDDEN_RE.search(draft)
    ):
        scope_rewriter = await load_active_prompt("guard.scope_check")
        if scope_rewriter and retries < MAX_GUARDRAIL_RETRIES:
            try:
                formatted = scope_rewriter[0].replace("{{draft_response}}", draft)
                rewritten, _, _ = await call_claude(
                    system_prompt=formatted,
                    messages=[{"role": "user", "content": "Rewrite."}],
                    temperature=0.1,
                    max_tokens=1024,
                )
                draft = rewritten.strip()
                retries += 1
            except Exception as e:
                logger.warning(
                    "guardrail_rewrite_failed",
                    rule="scope_violation",
                    error_type=type(e).__name__,
                    error=str(e),
                )
                incidents.append({"reason": "scope_violation", "original": draft[:200]})

    # Check 4: crisis safety
    if state.get("phase") == "Кризис":
        crisis_guard = await load_active_prompt("guard.crisis_safety")
        if crisis_guard and retries < MAX_GUARDRAIL_RETRIES:
            try:
                formatted = crisis_guard[0].replace("{{draft_response}}", draft)
                check_result, _, _ = await call_claude(
                    system_prompt=formatted,
                    messages=[{"role": "user", "content": "Check safety."}],
                    temperature=0.1,
                    max_tokens=512,
                )
                import json
                try:
                    safety = json.loads(check_result)
                except json.JSONDecodeError:
                    safety = {}
                if not safety.get("safe"):
                    incidents.append({"reason": "crisis_safety", "detail": safety})
            except Exception as e:
                logger.warning(
                    "guardrail_check_failed",
                    rule="crisis_safety",
                    error_type=type(e).__name__,
                    error=str(e),
                )

    state["validated_response"] = draft
    state["guardrail_retries"] = retries
    state["guardrail_incidents"] = incidents
    return state


async def persist_turn(state: PitchWowState) -> dict[str, Any]:
    return state


async def schedule_background_jobs(state: PitchWowState) -> PitchWowState:
    """
    Schedule background jobs: Cartographer (after calibration),
    Assembler (when sufficient material), and handle cross-sell.
    """
    from uuid import uuid4

    messages = state.get("messages", [])
    user_msg_count = len([m for m in messages if m["role"] == "user"])

    # Schedule Cartographer after 5+ user messages
    if user_msg_count >= 5 and state.get("phase") not in ("Кризис",):
        try:
            from app.db.models import Job as JobModel
            from app.db.session import async_session_factory

            async with async_session_factory() as db:
                session_uuid = uuid4()
                if state.get("session_id"):
                    session_uuid = uuid4()  # Use real UUID if available

                db.add(JobModel(
                    id=uuid4(),
                    type="cartographer",
                    status="pending",
                    session_id=session_uuid,
                    payload={"user_msg_count": user_msg_count},
                ))
                await db.commit()
        except Exception as e:
            logger.warning("background_job_schedule_failed", error_type=type(e).__name__, error=str(e))

    # Cross-sell handoff: if session completed and cross_sell_readiness == "ready"
    if (state.get("outcome") == "completed"
            and state.get("cross_sell_readiness") == "ready"
            and state.get("next_node_hypothesis") not in ("none", None)):

        next_node = state.get("next_node_hypothesis", "")
        node_descriptions = {
            "Беруни": "Беруни делает Insta-аудит SMM — поможет разобраться с визуалом и охватами.",
            "Навои": "Навои — контент-завод: системная упаковка смыслов в контент.",
            "Улугбек": "Улугбек — аналитика и A2A: метрики, воронки, автоматизации.",
        }
        desc = node_descriptions.get(next_node, "")

        current_response = state.get("validated_response") or state.get("pending_response") or ""
        cross_sell_msg = (
            f"\n\nКстати, если хочешь следующий шаг — {next_node} может быть полезен: {desc} "
            f"Ссылку на оплату отправит сам {next_node}, а не я. Решение за тобой."
        )
        state["validated_response"] = current_response + cross_sell_msg

    return state


def build_graph():
    builder = StateGraph(PitchWowState)

    builder.add_node("normalize_turn", normalize_turn)
    builder.add_node("load_runtime_settings", load_runtime_settings)
    builder.add_node("classify_incoming", classify_incoming)
    builder.add_node("update_calibration", update_calibration)
    builder.add_node("crisis_node", crisis_node)
    builder.add_node("defense_node", defense_node)
    builder.add_node("wings_interviewer_node", wings_interviewer_node)
    builder.add_node("guardrails_subgraph", guardrails_subgraph)
    builder.add_node("persist_turn", persist_turn)
    builder.add_node("schedule_background_jobs", schedule_background_jobs)

    builder.set_entry_point("normalize_turn")
    builder.add_edge("normalize_turn", "load_runtime_settings")
    builder.add_edge("load_runtime_settings", "classify_incoming")
    builder.add_edge("classify_incoming", "update_calibration")

    builder.add_conditional_edges(
        "update_calibration",
        route_by_phase,
        {
            "crisis_node": "crisis_node",
            "defense_node": "defense_node",
            "wings_interviewer_node": "wings_interviewer_node",
        },
    )

    builder.add_edge("crisis_node", "guardrails_subgraph")
    builder.add_edge("defense_node", "guardrails_subgraph")
    builder.add_edge("wings_interviewer_node", "guardrails_subgraph")

    builder.add_edge("guardrails_subgraph", "persist_turn")
    builder.add_edge("persist_turn", "schedule_background_jobs")
    builder.add_edge("schedule_background_jobs", END)

    return builder


def compile_graph():
    builder = build_graph()
    try:
        checkpointer = PostgresSaver.from_conn_string(config.database_url)
        graph = builder.compile(checkpointer=checkpointer)
        return graph
    except Exception as e:
        logger.warning("postgres_checkpointer_unavailable", error_type=type(e).__name__, error=str(e))
        return builder.compile()
