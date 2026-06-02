import structlog
from anthropic import AsyncAnthropic

from app.config import config

logger = structlog.get_logger()

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=config.anthropic_api_key)
    return _client


async def call_claude(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> tuple[str, int, int]:
    """
    Call Anthropic Claude API.
    Returns (response_text, input_tokens, output_tokens).
    """
    client = get_client()
    model = model or config.anthropic_primary_model

    # Convert messages to Anthropic format
    anthropic_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        anthropic_messages.append({
            "role": "user" if role in ("user", "system") else "assistant",
            "content": msg.get("content", ""),
        })

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=anthropic_messages,
    )

    content = response.content[0].text if response.content else ""
    input_tokens = response.usage.input_tokens if response.usage else 0
    output_tokens = response.usage.output_tokens if response.usage else 0

    logger.info(
        "claude_call_completed",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return content, input_tokens, output_tokens
