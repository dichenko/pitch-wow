from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import config

engine = create_async_engine(
    config.database_url.replace("postgresql+psycopg://", "postgresql+asyncpg://"),
    echo=False,
    pool_size=20,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
