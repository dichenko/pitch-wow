import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update

from app.db.models import Artifact, Job, Message, NaturalFeature, Session
from app.db.session import async_session_factory
from app.worker.jobs import run_assembler, run_cartographer

logger = structlog.get_logger()


async def process_job(job: Job):
    async with async_session_factory() as db:
        job.status = "running"
        job.attempts += 1
        job.updated_at = datetime.now(UTC)
        await db.commit()

        try:
            if job.type == "cartographer":
                await process_cartographer(db, job)
            elif job.type == "assembler":
                await process_assembler(db, job)
            elif job.type == "summarizer":
                await process_summarizer(db, job)

            job.status = "done"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            logger.error("job_failed", job_type=job.type, error=str(e))

        job.updated_at = datetime.now(UTC)
        await db.commit()


async def process_cartographer(db, job: Job):
    if not job.session_id:
        return

    # Get session transcript
    result = await db.execute(
        select(Message)
        .where(Message.session_id == job.session_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    transcript = "\n".join(f"[{m.role}]: {m.content}" for m in messages)

    session = await db.get(Session, job.session_id)
    state_json = session.state_json if session else {}

    features = await run_cartographer(transcript, state_json)

    for f in features:
        db.add(NaturalFeature(
            session_id=job.session_id,
            name=f.get("name", ""),
            description=f.get("description", ""),
            evidence_quotes=f.get("evidence_quotes", []),
            confidence=f.get("confidence", 0.0),
            axis=f.get("axis"),
            notes_for_assembler=f.get("notes_for_assembler", ""),
        ))

    job.result = {"features_count": len(features)}
    logger.info("cartographer_completed", session_id=str(job.session_id), features=len(features))


async def process_assembler(db, job: Job):
    payload = job.payload or {}
    session_artifact = payload.get("session_artifact", {})
    natural_features = payload.get("natural_features", [])

    result = await run_assembler(session_artifact, natural_features)

    if job.session_id and result:
        landing_tz = result.get("landing_tz_for_claude_design", "")
        if landing_tz:
            db.add(Artifact(
                session_id=job.session_id,
                artifact_type="landing_tz_for_claude_design",
                content_md=landing_tz,
                content_json=result,
                personality_dev_level=result.get("positioning_mode"),
                next_node_hypothesis=result.get("next_node_hypothesis", "none"),
            ))

        deck_tz = result.get("investor_deck_tz")
        if deck_tz:
            db.add(Artifact(
                session_id=job.session_id,
                artifact_type="investor_deck_tz",
                content_md=deck_tz,
            ))

        # Update session with next node hypothesis and cross-sell readiness
        if result.get("next_node_hypothesis"):
            await db.execute(
                update(Session)
                .where(Session.id == job.session_id)
                .values(
                    next_node_hypothesis=result["next_node_hypothesis"],
                    cross_sell_readiness="ready" if result["next_node_hypothesis"] != "none" else "conditional",
                    updated_at=datetime.now(UTC),
                )
            )

    job.result = result
    logger.info("assembler_completed", session_id=str(job.session_id))


async def process_summarizer(db, job: Job):
    from app.worker.jobs import run_session_summarizer
    if not job.session_id:
        return

    result = await db.execute(
        select(Message)
        .where(Message.session_id == job.session_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    transcript = "\n".join(f"[{m.role}]: {m.content}" for m in messages)

    summary = await run_session_summarizer(transcript)
    if summary:
        await db.execute(
            update(Session)
            .where(Session.id == job.session_id)
            .values(
                summary=summary.get("summary", ""),
                state_json=summary,
                updated_at=datetime.now(UTC),
            )
        )

    job.result = summary


async def main():
    logger.info("pitch_wow_worker_started")

    while True:
        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(Job)
                    .where(
                        Job.status == "pending",
                        Job.run_after <= datetime.now(UTC),
                        Job.attempts < Job.max_attempts,
                    )
                    .order_by(Job.run_after.asc())
                    .limit(5)
                )
                jobs = result.scalars().all()

                for job in jobs:
                    await process_job(job)

            await asyncio.sleep(2)
        except Exception as e:
            logger.error("worker_loop_error", error=str(e))
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
