import redis.asyncio as aioredis
import structlog

from app.config import config

logger = structlog.get_logger()

LOCK_TTL = 30


async def acquire_lock(telegram_user_id: int) -> bool:
    """Acquire distributed lock for turn processing."""
    try:
        r = aioredis.from_url(config.redis_url)
        key = f"lock:turn:{telegram_user_id}"
        acquired = await r.set(key, "1", nx=True, ex=LOCK_TTL)
        await r.aclose()
        return bool(acquired)
    except Exception:
        return True  # If Redis is down, allow processing (degraded mode)


async def release_lock(telegram_user_id: int):
    """Release distributed lock."""
    try:
        r = aioredis.from_url(config.redis_url)
        key = f"lock:turn:{telegram_user_id}"
        await r.delete(key)
        await r.aclose()
    except Exception:
        pass
