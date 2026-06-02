import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GuardrailIncident,
    Message,
    Prompt,
    RuntimeSetting,
    Session,
)


class PromptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self, key: str) -> Prompt | None:
        result = await self.session.execute(
            select(Prompt).where(Prompt.key == key, Prompt.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_by_key(self, key: str) -> list[Prompt]:
        result = await self.session.execute(
            select(Prompt).where(Prompt.key == key).order_by(Prompt.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_version(self, key: str, content: str, title: str, updated_by: str) -> Prompt:
        current = await self.get_active(key)
        version_num = "0.1"
        if current:
            parts = current.version.split(".")
            version_num = f"{parts[0]}.{int(parts[1]) + 1}"

        prompt = Prompt(
            id=uuid.uuid4(),
            key=key,
            type=current.type if current else "system",
            version=version_num,
            title=title,
            content=content,
            is_active=False,
            updated_by=updated_by,
            created_by=updated_by,
        )
        self.session.add(prompt)
        return prompt

    async def activate(self, prompt_id: uuid.UUID):
        prompt = await self.session.get(Prompt, prompt_id)
        if not prompt:
            return
        await self.session.execute(
            update(Prompt).where(Prompt.key == prompt.key, Prompt.is_active.is_(True)).values(is_active=False)
        )
        prompt.is_active = True


class SessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        return await self.session.get(Session, session_id)

    async def get_active_by_chat(self, telegram_chat_id: int) -> Session | None:
        result = await self.session.execute(
            select(Session).where(
                Session.telegram_chat_id == telegram_chat_id,
                Session.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def create(self, tg_user_id: int, telegram_chat_id: int) -> Session:
        session = Session(
            tg_user_id=tg_user_id,
            telegram_chat_id=telegram_chat_id,
            langgraph_thread_id=f"telegram:{telegram_chat_id}:session:{uuid.uuid4()}",
        )
        self.session.add(session)
        return session

    async def update_phase(self, session_id: uuid.UUID, phase: str, confidence: float):
        await self.session.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(
                phase=phase,
                phase_confidence=confidence,
                phase_calibrated_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

    async def complete(self, session_id: uuid.UUID, outcome: str):
        await self.session.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(
                status="completed",
                outcome=outcome,
                completed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Message:
        msg = Message(**kwargs)
        self.session.add(msg)
        return msg

    async def list_by_session(self, session_id: uuid.UUID, limit: int = 50) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class GuardrailIncidentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> GuardrailIncident:
        incident = GuardrailIncident(**kwargs)
        self.session.add(incident)
        return incident


class RuntimeSettingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> RuntimeSetting | None:
        return await self.session.get(RuntimeSetting, key)

    async def set(self, key: str, value: dict, updated_by: str):
        setting = await self.get(key)
        if setting:
            setting.value = value
            setting.updated_by = updated_by
            setting.updated_at = datetime.now(UTC)
        else:
            setting = RuntimeSetting(key=key, value=value, updated_by=updated_by)
            self.session.add(setting)
