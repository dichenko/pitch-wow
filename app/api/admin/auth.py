from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyCookie
from itsdangerous import URLSafeTimedSerializer
from pydantic import BaseModel

from app.config import config

serializer = URLSafeTimedSerializer(config.admin_session_secret)
cookie_scheme = APIKeyCookie(name="pitchwow_session", auto_error=False)

SESSION_MAX_AGE = timedelta(hours=config.admin_session_max_age_hours)


class AdminSession(BaseModel):
    telegram_user_id: int
    role: str


async def get_current_admin(
    request: Request, cookie: str | None = Depends(cookie_scheme)
) -> AdminSession:
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        data = serializer.loads(cookie, max_age=int(SESSION_MAX_AGE.total_seconds()))
        return AdminSession(**data)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Session expired or invalid") from e


def create_session_token(telegram_user_id: int, role: str = "admin") -> str:
    """Sign a session cookie payload using ADMIN_SESSION_SECRET."""
    return serializer.dumps({"telegram_user_id": telegram_user_id, "role": role})
