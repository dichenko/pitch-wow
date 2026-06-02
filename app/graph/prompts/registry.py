import structlog
from sqlalchemy import select

from app.db.models import Prompt
from app.db.session import async_session_factory

logger = structlog.get_logger()

# In-memory cache for active prompts
_cache: dict[str, tuple[str, str, str]] = {}  # key -> (content, version, type)


async def load_active_prompt(key: str) -> tuple[str, str, str] | None:
    """Load active prompt from DB. Returns (content, version, type) or None."""
    if key in _cache:
        return _cache[key]

    async with async_session_factory() as session:
        result = await session.execute(
            select(Prompt).where(Prompt.key == key, Prompt.is_active.is_(True))
        )
        prompt = result.scalar_one_or_none()
        if prompt:
            _cache[key] = (prompt.content, prompt.version, prompt.type)
            return _cache[key]

    return None


async def load_all_active_prompts() -> dict[str, tuple[str, str, str]]:
    """Preload all active prompts into cache."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Prompt).where(Prompt.is_active.is_(True))
        )
        for prompt in result.scalars().all():
            _cache[prompt.key] = (prompt.content, prompt.version, prompt.type)
    return _cache


def get_cached_prompt(key: str) -> tuple[str, str, str] | None:
    """Get prompt from cache without DB call."""
    return _cache.get(key)


def invalidate_cache(key: str | None = None):
    """Invalidate prompt cache for hot-reload."""
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
