import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


# ── tg_users ────────────────────────────────────────────────────────────────

class TgUser(Base):
    __tablename__ = "tg_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    language_code: Mapped[str | None] = mapped_column(Text)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    voice_reply_mode: Mapped[str] = mapped_column(
        String, default="auto", nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    sessions: Mapped[list["Session"]] = relationship(back_populates="tg_user")


# ── sessions ────────────────────────────────────────────────────────────────

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_users.id"), nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    phase: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
    phase_confidence: Mapped[float | None] = mapped_column(Float)
    phase_calibrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    personality_dev_level: Mapped[str | None] = mapped_column(String)
    personality_confidence: Mapped[float | None] = mapped_column(Float)

    current_stage: Mapped[str] = mapped_column(String, default="opening", nullable=False)
    current_substage: Mapped[str | None] = mapped_column(String)

    a3_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repeated_question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    macro_pattern_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    investor_situation: Mapped[str] = mapped_column(String, default="отсутствует", nullable=False)
    target_investor_hint: Mapped[str | None] = mapped_column(String)

    cross_sell_readiness: Mapped[str] = mapped_column(String, default="not-ready", nullable=False)
    next_node_hypothesis: Mapped[str] = mapped_column(String, default="none", nullable=False)

    outcome: Mapped[str | None] = mapped_column(String)

    state_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)

    langgraph_thread_id: Mapped[str | None] = mapped_column(Text, unique=True)
    langsmith_thread_id: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    tg_user: Mapped["TgUser"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")
    guardrail_incidents: Mapped[list["GuardrailIncident"]] = relationship(back_populates="session")
    natural_features: Mapped[list["NaturalFeature"]] = relationship(back_populates="session")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="session")
    jobs: Mapped[list["Job"]] = relationship(back_populates="session")


# ── messages ────────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False,
    )

    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, default="text", nullable=False)

    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_file_id: Mapped[str | None] = mapped_column(Text)

    stt_provider: Mapped[str | None] = mapped_column(Text)
    stt_model: Mapped[str | None] = mapped_column(Text)
    stt_confidence: Mapped[float | None] = mapped_column(Float)
    raw_stt_response: Mapped[dict | None] = mapped_column(JSON)

    tts_provider: Mapped[str | None] = mapped_column(Text)
    tts_voice: Mapped[str | None] = mapped_column(Text)
    tts_audio_path: Mapped[str | None] = mapped_column(Text)

    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    token_input: Mapped[int | None] = mapped_column(Integer)
    token_output: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    langsmith_trace_id: Mapped[str | None] = mapped_column(Text)
    langsmith_run_id: Mapped[str | None] = mapped_column(Text)

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="messages")


# ── prompts ─────────────────────────────────────────────────────────────────

class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_override: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[float | None] = mapped_column(Float)
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    json_schema: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    changelog: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("key", "version"),
    )


# ── runtime_settings ────────────────────────────────────────────────────────

class RuntimeSetting(Base):
    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# ── guardrail_incidents ─────────────────────────────────────────────────────

class GuardrailIncident(Base):
    __tablename__ = "guardrail_incidents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"),
    )
    message_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("messages.id", ondelete="SET NULL"))

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    original_response: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_response: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    langsmith_trace_id: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="guardrail_incidents")


# ── natural_features ────────────────────────────────────────────────────────

class NaturalFeature(Base):
    __tablename__ = "natural_features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    evidence_quotes: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    axis: Mapped[str | None] = mapped_column(String)
    notes_for_assembler: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(Text, default="cartographer", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="natural_features")


# ── artifacts ───────────────────────────────────────────────────────────────

class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False,
    )

    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict | None] = mapped_column(JSON)
    file_path: Mapped[str | None] = mapped_column(Text)
    public_url: Mapped[str | None] = mapped_column(Text)

    personality_dev_level: Mapped[str | None] = mapped_column(String)
    investor_situation: Mapped[str | None] = mapped_column(String)
    cross_sell_readiness: Mapped[str | None] = mapped_column(String)
    next_node_hypothesis: Mapped[str | None] = mapped_column(String)

    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="artifacts")


# ── jobs ────────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"),
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="jobs")


# ── admin_users ─────────────────────────────────────────────────────────────

class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String, default="admin", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# ── audit_log ───────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
