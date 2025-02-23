"""Unit of work pattern implementation."""
from types import TracebackType
from typing import Optional, Type
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.repositories import CollectionRepository, FaceRepository


class UnitOfWork:
    """Unit of work for managing database transactions and repositories."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize unit of work.
        
        Args:
            session: Database session
        """
        self._session = session
        self.collections = CollectionRepository(session)
        self.faces = FaceRepository(session)

    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context manager.
        
        Returns:
            UnitOfWork: Self
        """
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit async context manager.
        
        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred
        """
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self._session.rollback()

    @asynccontextmanager
    async def transaction(self):
        """Create a new transaction scope.
        
        Example:
            ```python
            async with uow.transaction():
                # do some work
                # transaction will be committed if no exceptions
                # or rolled back if an exception occurs
            ```
        """
        try:
            yield self
            await self.commit()
        except Exception:
            await self.rollback()
            raise 