from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.admin.routes import router as admin_router
from app.config import config
from app.db.session import engine

app = FastAPI(title="Pitch Wow API", version="0.1.0")
app.include_router(admin_router)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "env": config.app_env})


@app.get("/health/db")
async def health_db():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


@app.get("/health/redis")
async def health_redis():
    import redis.asyncio as aioredis
    try:
        r = aioredis.from_url(config.redis_url)
        await r.ping()
        await r.aclose()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


@app.get("/health/langsmith")
async def health_langsmith():
    if config.langsmith_tracing:
        return JSONResponse({"status": "enabled", "project": config.langsmith_project})
    return JSONResponse({"status": "disabled"})
