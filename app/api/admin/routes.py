from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy import select

from app.api.admin.auth import (
    SESSION_MAX_AGE,
    AdminSession,
    create_session_token,
    get_current_admin,
    serializer,
)
from app.db.models import GuardrailIncident, Prompt, RuntimeSetting, Session
from app.db.session import async_session_factory

templates = None


def get_templates():
    global templates
    if templates is None:
        from fastapi.templating import Jinja2Templates
        templates = Jinja2Templates(directory="app/api/admin/templates")
    return templates


router = APIRouter(prefix="/admin")


# ── Login flow (via Telegram bot /admin command) ────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show info page explaining how to obtain access via Telegram bot."""
    tpl = get_templates()
    return tpl.TemplateResponse("login.html", {"request": request})


@router.get("/login/token", response_class=HTMLResponse)
async def login_via_token(request: Request, token: str = ""):
    """
    Validate the signed token from the Telegram bot /admin command.
    On success: set session cookie and redirect to dashboard.
    On failure: show error page.
    """
    tpl = get_templates()
    max_age_seconds = int(SESSION_MAX_AGE.total_seconds())

    try:
        data = serializer.loads(token, max_age=max_age_seconds)
        telegram_user_id = int(data["telegram_user_id"])
    except SignatureExpired:
        return tpl.TemplateResponse(
            "login_message.html",
            {"request": request, "error": "Ссылка истекла. Отправьте /admin боту снова."},
            status_code=401,
        )
    except (BadSignature, KeyError, ValueError):
        return tpl.TemplateResponse(
            "login_message.html",
            {"request": request, "error": "Недействительная ссылка. Отправьте /admin боту снова."},
            status_code=401,
        )

    session_token = create_session_token(telegram_user_id)
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(
        "pitchwow_session",
        session_token,
        httponly=True,
        samesite="lax",
        max_age=max_age_seconds,
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/admin/login")
    response.delete_cookie("pitchwow_session")
    return response


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, admin: AdminSession = Depends(get_current_admin)):
    async with async_session_factory() as session:
        # Active sessions
        active_result = await session.execute(
            select(Session).where(Session.status == "active")
        )
        active_sessions = len(active_result.all())

        completed_result = await session.execute(
            select(Session).where(Session.status == "completed")
        )
        completed_sessions = len(completed_result.all())

        short_result = await session.execute(
            select(Session).where(Session.outcome == "short-session")
        )
        short_sessions = len(short_result.all())

        crisis_result = await session.execute(
            select(Session).where(Session.outcome == "crisis-walk-away")
        )
        crisis_walk_aways = len(crisis_result.all())

        # Phase distribution
        phases = {"unknown": 0, "Защита": 0, "Кризис": 0, "Крылья": 0}
        phase_result = await session.execute(select(Session.phase))
        for row in phase_result.all():
            if row[0] in phases:
                phases[row[0]] += 1

        personality_levels = {"личность": 0, "бизнес": 0, "синергия": 0}
        pers_result = await session.execute(select(Session.personality_dev_level))
        for row in pers_result.all():
            if row[0] in personality_levels:
                personality_levels[row[0]] += 1

    tpl = get_templates()
    return tpl.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "admin": admin,
            "stats": {
                "active_sessions": active_sessions,
                "completed_sessions": completed_sessions,
                "short_sessions": short_sessions,
                "crisis_walk_aways": crisis_walk_aways,
                "phases": phases,
                "personality_levels": personality_levels,
            },
        },
    )


# ── Prompts ─────────────────────────────────────────────────────────────────

@router.get("/prompts", response_class=HTMLResponse)
async def list_prompts(request: Request, admin: AdminSession = Depends(get_current_admin)):
    async with async_session_factory() as session:
        result = await session.execute(select(Prompt).order_by(Prompt.key, Prompt.created_at.desc()))
        prompts = result.scalars().all()

    tpl = get_templates()
    return tpl.TemplateResponse("prompts_list.html", {"request": request, "admin": admin, "prompts": prompts})


@router.get("/prompts/{key}", response_class=HTMLResponse)
async def prompt_detail(request: Request, key: str, admin: AdminSession = Depends(get_current_admin)):
    async with async_session_factory() as session:
        result = await session.execute(
            select(Prompt).where(Prompt.key == key, Prompt.is_active.is_(True))
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            result = await session.execute(
                select(Prompt).where(Prompt.key == key).order_by(Prompt.created_at.desc()).limit(1)
            )
            prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(status_code=404)

    tpl = get_templates()
    return tpl.TemplateResponse("prompt_detail.html", {"request": request, "admin": admin, "prompt": prompt})


@router.post("/prompts/{key}/versions")
async def create_prompt_version(
    request: Request,
    key: str,
    title: str = Form(...),
    content: str = Form(...),
    admin: AdminSession = Depends(get_current_admin),
):
    from uuid import uuid4
    async with async_session_factory() as session:
        result = await session.execute(
            select(Prompt).where(Prompt.key == key).order_by(Prompt.created_at.desc()).limit(1)
        )
        latest = result.scalar_one_or_none()
        version = "0.1"
        ptype = "system"
        if latest:
            parts = latest.version.split(".")
            version = f"{parts[0]}.{int(parts[1]) + 1}"
            ptype = latest.type

        prompt = Prompt(
            id=uuid4(),
            key=key,
            type=ptype,
            version=version,
            title=title,
            content=content,
            is_active=False,
            updated_by=str(admin.telegram_user_id),
            created_by=str(admin.telegram_user_id),
        )
        session.add(prompt)
        await session.commit()

    return RedirectResponse(url=f"/admin/prompts/{key}", status_code=303)


@router.get("/prompts/{prompt_id}/activate")
async def activate_prompt(prompt_id: str, admin: AdminSession = Depends(get_current_admin)):
    from uuid import UUID

    from sqlalchemy import update

    async with async_session_factory() as session:
        prompt = await session.get(Prompt, UUID(prompt_id))
        if not prompt:
            raise HTTPException(status_code=404)

        await session.execute(
            update(Prompt)
            .where(Prompt.key == prompt.key, Prompt.is_active.is_(True))
            .values(is_active=False)
        )
        prompt.is_active = True
        prompt.updated_by = str(admin.telegram_user_id)
        prompt.updated_at = datetime.now(UTC)
        await session.commit()

    return RedirectResponse(url=f"/admin/prompts/{prompt.key}", status_code=303)


# ── Sessions ────────────────────────────────────────────────────────────────

@router.get("/sessions", response_class=HTMLResponse)
async def list_sessions(request: Request, admin: AdminSession = Depends(get_current_admin)):
    async with async_session_factory() as session:
        result = await session.execute(
            select(Session).order_by(Session.updated_at.desc()).limit(100)
        )
        sessions = result.scalars().all()

    tpl = get_templates()
    return tpl.TemplateResponse(
        "sessions_list.html",
        {
            "request": request,
            "admin": admin,
            "sessions": [
                {
                    "user_name": f"user:{s.telegram_chat_id}",
                    "telegram_chat_id": s.telegram_chat_id,
                    "status": s.status,
                    "phase": s.phase,
                    "personality_dev_level": s.personality_dev_level,
                    "msg_count": 0,
                    "last_message_at": str(s.last_message_at)[:19] if s.last_message_at else None,
                    "outcome": s.outcome,
                    "next_node_hypothesis": s.next_node_hypothesis,
                }
                for s in sessions
            ],
        },
    )


# ── Settings ────────────────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def list_settings(request: Request, admin: AdminSession = Depends(get_current_admin)):
    async with async_session_factory() as session:
        result = await session.execute(select(RuntimeSetting).order_by(RuntimeSetting.key))
        settings = result.scalars().all()

    tpl = get_templates()
    return tpl.TemplateResponse(
        "settings_list.html",
        {
            "request": request,
            "admin": admin,
            "settings": [
                {
                    "key": s.key,
                    "value": str(s.value),
                    "description": s.description,
                    "updated_at": str(s.updated_at)[:19],
                }
                for s in settings
            ],
        },
    )


# ── Incidents ───────────────────────────────────────────────────────────────

@router.get("/incidents", response_class=HTMLResponse)
async def list_incidents(request: Request, admin: AdminSession = Depends(get_current_admin)):
    async with async_session_factory() as session:
        result = await session.execute(
            select(GuardrailIncident).order_by(GuardrailIncident.created_at.desc()).limit(100)
        )
        incidents = result.scalars().all()

    tpl = get_templates()
    return tpl.TemplateResponse(
        "incidents_list.html",
        {
            "request": request,
            "admin": admin,
            "incidents": [
                {
                    "reason": i.reason,
                    "session_id": str(i.session_id)[:8] if i.session_id else "-",
                    "retry_count": i.retry_count,
                    "resolved": i.resolved,
                    "created_at": str(i.created_at)[:19],
                }
                for i in incidents
            ],
        },
    )
