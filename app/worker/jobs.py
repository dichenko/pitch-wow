import json

import structlog

from app.config import config
from app.graph.prompts.registry import load_active_prompt
from app.services.anthropic_client import call_claude

logger = structlog.get_logger()


async def run_cartographer(transcript: str, state_json: dict) -> list[dict]:
    """
    Extract natural features from session transcript.
    Returns list of feature dicts.
    """
    prompt = await load_active_prompt("cartographer.system")
    if not prompt:
        logger.warning("cartographer_prompt_not_found")
        return []

    formatted_prompt = prompt[0].replace("{{transcript}}", transcript).replace(
        "{{state}}", json.dumps(state_json, ensure_ascii=False, indent=2)
    )

    try:
        response, _, _ = await call_claude(
            system_prompt=formatted_prompt,
            messages=[{"role": "user", "content": "Extract features."}],
            model=config.anthropic_classifier_model,
            temperature=0.2,
            max_tokens=2048,
        )

        json_match = response.strip()
        if "```json" in json_match:
            json_match = json_match.split("```json")[1].split("```")[0]
        elif "```" in json_match:
            json_match = json_match.split("```")[1].split("```")[0]

        result = json.loads(json_match.strip())
        return result.get("features", [])
    except Exception as e:
        logger.error("cartographer_error", error=str(e))
        return []


async def run_assembler(
    session_artifact: dict,
    natural_features: list[dict],
) -> dict:
    """
    Generate landing TZ and optional investor deck TZ.
    Returns dict with landing_tz_for_claude_design, investor_deck_tz, etc.
    """
    prompt = await load_active_prompt("assembler.system")
    if not prompt:
        logger.warning("assembler_prompt_not_found")
        return {}

    formatted_prompt = (
        prompt[0]
        .replace("{{session_artifact}}", json.dumps(session_artifact, ensure_ascii=False, indent=2))
        .replace("{{natural_features}}", json.dumps(natural_features, ensure_ascii=False, indent=2))
    )

    try:
        response, _, _ = await call_claude(
            system_prompt=formatted_prompt,
            messages=[{"role": "user", "content": "Assemble output."}],
            temperature=0.3,
            max_tokens=4096,
        )

        json_match = response.strip()
        if "```json" in json_match:
            json_match = json_match.split("```json")[1].split("```")[0]
        elif "```" in json_match:
            json_match = json_match.split("```")[1].split("```")[0]

        return json.loads(json_match.strip())
    except Exception as e:
        logger.error("assembler_error", error=str(e))
        return {}


async def run_session_summarizer(transcript: str) -> dict:
    prompt = await load_active_prompt("summarizer.session")
    if not prompt:
        return {}

    try:
        response, _, _ = await call_claude(
            system_prompt=prompt[0],
            messages=[{"role": "user", "content": f"Transcript:\n{transcript}"}],
            temperature=0.2,
            max_tokens=1024,
        )
        json_match = response.strip()
        if "```json" in json_match:
            json_match = json_match.split("```json")[1].split("```")[0]
        return json.loads(json_match.strip())
    except Exception:
        return {}
