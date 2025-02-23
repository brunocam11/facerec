"""Database repositories for face recognition service."""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import CollectionNotFoundError
from app.infrastructure.database.models import Collection, Face


class CollectionRepository:
    """Repository for collection operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.
        
        Args:
            session: Database session
        """
        self._session = session

    async def get_by_external_id(self, external_id: str) -> Collection:
        """Get collection by external ID.
        
        Args:
            external_id: External system collection identifier
            
        Returns:
            Collection: Found collection
            
        Raises:
            CollectionNotFoundError: If collection not found
        """
        stmt = select(Collection).where(Collection.external_id == external_id)
        result = await self._session.execute(stmt)
        collection = result.scalar_one_or_none()
        
        if not collection:
            raise CollectionNotFoundError(f"Collection not found: {external_id}")
        
        return collection

    async def get_or_create(self, external_id: str, metadata: dict = None) -> Collection:
        """Get collection by external ID or create if not exists.
        
        Args:
            external_id: External system collection identifier
            metadata: Optional metadata from external system
            
        Returns:
            Collection: Found or created collection
        """
        try:
            return await self.get_by_external_id(external_id)
        except CollectionNotFoundError:
            collection = Collection(
                external_id=external_id,
                metadata=metadata
            )
            self._session.add(collection)
            await self._session.flush()
            return collection


class FaceRepository:
    """Repository for face operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.
        
        Args:
            session: Database session
        """
        self._session = session

    async def create(
        self,
        collection_id: UUID,
        external_image_id: str,
        vector_id: str,
        confidence: float,
        bbox_left: float,
        bbox_top: float,
        bbox_width: float,
        bbox_height: float,
        metadata: dict = None
    ) -> Face:
        """Create a new face record.
        
        Args:
            collection_id: Internal collection ID
            external_image_id: External system image identifier
            vector_id: ID of the face vector in Pinecone
            confidence: Face detection confidence score
            bbox_left: Bounding box left coordinate
            bbox_top: Bounding box top coordinate
            bbox_width: Bounding box width
            bbox_height: Bounding box height
            metadata: Optional metadata from external system
            
        Returns:
            Face: Created face record
        """
        face = Face(
            collection_id=collection_id,
            external_image_id=external_image_id,
            vector_id=vector_id,
            confidence=confidence,
            bbox_left=bbox_left,
            bbox_top=bbox_top,
            bbox_width=bbox_width,
            bbox_height=bbox_height,
            metadata=metadata
        )
        self._session.add(face)
        await self._session.flush()
        return face

    async def get_by_vector_ids(self, vector_ids: List[str]) -> List[Face]:
        """Get faces by vector IDs.
        
        Args:
            vector_ids: List of vector IDs from Pinecone
            
        Returns:
            List[Face]: Found face records
        """
        stmt = (
            select(Face)
            .where(Face.vector_id.in_(vector_ids))
            .options(selectinload(Face.collection))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_external_image(
        self,
        external_image_id: str,
        collection_id: UUID
    ) -> List[Face]:
        """Get faces by external image ID and collection.
        
        Args:
            external_image_id: External system image identifier
            collection_id: Internal collection ID
            
        Returns:
            List[Face]: Found face records
        """
        stmt = (
            select(Face)
            .where(
                Face.external_image_id == external_image_id,
                Face.collection_id == collection_id
            )
            .options(selectinload(Face.collection))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_external_image(
        self,
        external_image_id: str,
        collection_id: UUID
    ) -> List[str]:
        """Delete faces by external image ID and collection.
        
        Args:
            external_image_id: External system image identifier
            collection_id: Internal collection ID
            
        Returns:
            List[str]: Vector IDs of deleted faces
        """
        # Get vector IDs first for cleanup in vector store
        faces = await self.get_by_external_image(external_image_id, collection_id)
        vector_ids = [face.vector_id for face in faces]
        
        # Delete faces
        stmt = (
            select(Face)
            .where(
                Face.external_image_id == external_image_id,
                Face.collection_id == collection_id
            )
        )
        await self._session.execute(stmt.delete())
        
        return vector_ids 