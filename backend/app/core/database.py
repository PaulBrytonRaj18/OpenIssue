import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DATABASE_URL = settings.DATABASE_URL
if "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
    connect_args={"timeout": 10, "statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Ensure DB extensions exist. Tables are managed by Alembic migrations."""
    try:
        async with engine.begin() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
        logger.info("Database extension verified")
    except Exception as e:
        logger.warning("Could not create vector extension (managed PG?): %s", e)

    try:
        from app.models import models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified (via create_all)")
        logger.warning(
            "Using create_all — production deployments should use: alembic upgrade head"
        )
    except Exception as e:
        logger.info("Table creation deferred to Alembic: %s", e)
