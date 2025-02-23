"""Database dependencies for FastAPI."""
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.unit_of_work import UnitOfWork


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with get_db_session() as session:
        yield session


async def get_uow(
    session: AsyncSession = Depends(get_session)
) -> AsyncGenerator[UnitOfWork, None]:
    """Get unit of work.
    
    Args:
        session: Database session
        
    Yields:
        UnitOfWork: Unit of work instance
    """
    async with UnitOfWork(session) as uow:
        yield uow 