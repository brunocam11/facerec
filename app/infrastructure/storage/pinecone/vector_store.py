"""Pinecone implementation of vector store for face embeddings."""
import logging
from typing import Dict, List, Optional
from uuid import UUID

import pinecone
from pinecone import Index
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import CollectionNotFoundError, VectorStoreError
from app.core.logging import get_logger
from app.domain.entities.face import Face
from app.domain.interfaces.storage.vector_store import VectorStore
from app.domain.value_objects.recognition import FaceMatch, SearchResult

logger = get_logger(__name__)


class PineconeMetadata(BaseModel):
    """Metadata stored with each vector in Pinecone."""
    face_detection_id: UUID  # ID from the marketplace database
    image_id: UUID  # ID from the marketplace database
    collection_id: UUID  # ID from the marketplace database
    confidence: float
    bounding_box: Dict[str, float]


class PineconeVectorStore(VectorStore):
    """Pinecone implementation of vector store for face embeddings."""

    def __init__(self) -> None:
        """Initialize Pinecone client and index."""
        try:
            # Initialize Pinecone
            pinecone.init(
                api_key=settings.PINECONE_API_KEY,
                environment=settings.PINECONE_ENVIRONMENT
            )

            # Get or create index
            self.index_name = settings.PINECONE_INDEX_NAME
            self.index: Index = pinecone.Index(self.index_name)
            logger.info(
                "Pinecone vector store initialized",
                index=self.index_name
            )

        except Exception as e:
            logger.error(
                "Failed to initialize Pinecone",
                error=str(e),
                exc_info=True
            )
            raise VectorStoreError(f"Failed to initialize Pinecone: {str(e)}")

    async def store_face(
        self,
        face: Face,
        album_id: UUID,
        image_id: UUID,
        face_detection_id: UUID,
    ) -> None:
        """Store a face embedding in an album.
        
        Args:
            face: Face object containing embedding and metadata
            album_id: Album ID from the marketplace
            image_id: Image ID from the marketplace
            face_detection_id: Face detection ID from the marketplace
        """
        try:
            # Use face_detection_id as vector ID for direct lookups
            vector_id = str(face_detection_id)

            # Prepare metadata
            metadata = PineconeMetadata(
                face_detection_id=face_detection_id,
                image_id=image_id,
                collection_id=album_id,
                confidence=face.confidence,
                bounding_box=face.bounding_box.dict()
            )

            # Upsert the embedding with metadata
            self.index.upsert(
                vectors=[(
                    vector_id,
                    face.embedding,
                    metadata.dict()
                )]
            )

            logger.debug(
                "Stored face embedding",
                face_detection_id=face_detection_id,
                album_id=album_id,
                image_id=image_id
            )

        except Exception as e:
            logger.error(
                "Failed to store face embedding",
                error=str(e),
                face_detection_id=face_detection_id,
                album_id=album_id,
                image_id=image_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to store face embedding: {str(e)}")

    async def search_faces(
        self,
        query_face: Face,
        album_id: UUID,
        similarity_threshold: Optional[float] = None,
        max_matches: Optional[int] = None,
    ) -> SearchResult:
        """Search for similar faces in an album."""
        try:
            # Set defaults from settings
            threshold = similarity_threshold or settings.SIMILARITY_THRESHOLD
            limit = max_matches or settings.MAX_MATCHES

            # Query Pinecone with metadata filter for album
            results = self.index.query(
                vector=query_face.embedding,
                filter={"collection_id": str(album_id)},
                top_k=limit,
                include_metadata=True
            )

            # Convert results to domain model
            matches = []
            for match in results.matches:
                # Skip results below threshold
                if match.score < (threshold / 100):  # Pinecone uses 0-1 scale
                    continue

                metadata = match.metadata
                face = Face(
                    bounding_box=metadata["bounding_box"],
                    confidence=metadata["confidence"],
                    embedding=match.values if hasattr(match, 'values') else None
                )

                matches.append(FaceMatch(
                    face=face,
                    similarity=match.score * 100,  # Convert to 0-100 scale
                    face_detection_id=UUID(metadata["face_detection_id"]),
                    image_id=UUID(metadata["image_id"])
                ))

            logger.debug(
                "Face search completed",
                album_id=album_id,
                matches_found=len(matches),
                threshold=threshold
            )

            return SearchResult(
                searched_face=query_face,
                matches=matches
            )

        except Exception as e:
            logger.error(
                "Face search failed",
                error=str(e),
                album_id=album_id,
                exc_info=True
            )
            raise VectorStoreError(f"Face search failed: {str(e)}")

    async def delete_face(
        self,
        image_id: UUID,
        album_id: UUID,
    ) -> None:
        """Delete face embeddings for an image from an album."""
        try:
            # Delete all vectors with matching image_id and album_id
            self.index.delete(
                filter={
                    "image_id": str(image_id),
                    "collection_id": str(album_id)
                }
            )

            logger.debug(
                "Deleted face embeddings",
                image_id=image_id,
                album_id=album_id
            )

        except Exception as e:
            logger.error(
                "Failed to delete face embeddings",
                error=str(e),
                image_id=image_id,
                album_id=album_id,
                exc_info=True
            )
            raise VectorStoreError(
                f"Failed to delete face embeddings: {str(e)}")

    async def delete_album(
        self,
        album_id: UUID,
    ) -> None:
        """Delete all face embeddings in an album."""
        try:
            # Delete all vectors with matching album_id
            self.index.delete(
                filter={"collection_id": str(album_id)}
            )

            logger.debug(
                "Deleted album embeddings",
                album_id=album_id
            )

        except Exception as e:
            logger.error(
                "Failed to delete album",
                error=str(e),
                album_id=album_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to delete album: {str(e)}")
