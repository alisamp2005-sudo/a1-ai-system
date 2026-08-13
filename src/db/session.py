"""Database session management."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.utils.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "debug",
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Dependency for FastAPI routes."""
    async with async_session_factory() as session:
        yield session
