"""Database session management."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.ENVIRONMENT == "development",
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_POOL_TIMEOUT
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        ```python
        async with get_db_session() as session:
            await session.execute(query)
            await session.commit()
        ```
    """
    session = async_session_factory()
    logger.debug("Creating new database session")
    try:
        yield session
    except Exception as e:
        logger.error(
            "Database session error",
            error=str(e),
            exc_info=True
        )
        await session.rollback()
        raise
    finally:
        logger.debug("Closing database session")
        await session.close() 