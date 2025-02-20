"""Pinecone implementation of vector store for face embeddings."""
import logging
from typing import Dict, List, Optional
from uuid import UUID

from pinecone import Pinecone
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import CollectionNotFoundError, VectorStoreError
from app.core.logging import get_logger
from app.domain.entities.face import Face, BoundingBox
from app.domain.interfaces.storage.vector_store import VectorStore
from app.domain.value_objects.recognition import FaceMatch, SearchResult

logger = get_logger(__name__)


class PineconeMetadata(BaseModel):
    """Metadata stored with each vector in Pinecone."""
    face_detection_id: str  # External system identifier for the face detection
    image_id: str  # External system identifier for the image
    collection_id: str  # External system identifier for the collection/album
    confidence: float
    # Flattened bounding box coordinates
    bbox_left: float
    bbox_top: float
    bbox_width: float
    bbox_height: float


class PineconeVectorStore(VectorStore):
    """Pinecone implementation of vector store for face embeddings."""

    def __init__(self) -> None:
        """Initialize Pinecone client and index."""
        try:
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)

            # Get or create index
            self.index_name = settings.PINECONE_INDEX_NAME
            self.index = pc.Index(self.index_name)
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
        collection_id: str,
        image_id: str,
        face_detection_id: str,
    ) -> None:
        """Store a face embedding in an album.
        
        Args:
            face: Face object containing embedding and metadata
            collection_id: External system collection/album identifier
            image_id: External system image identifier
            face_detection_id: External system face detection identifier
        """
        try:
            # Use face_detection_id as vector ID for direct lookups
            vector_id = face_detection_id

            # Prepare metadata with flattened bounding box
            metadata = PineconeMetadata(
                face_detection_id=face_detection_id,
                image_id=image_id,
                collection_id=collection_id,
                confidence=face.confidence,
                bbox_left=face.bounding_box.left,
                bbox_top=face.bounding_box.top,
                bbox_width=face.bounding_box.width,
                bbox_height=face.bounding_box.height
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
                collection_id=collection_id,
                image_id=image_id
            )

        except Exception as e:
            logger.error(
                "Failed to store face embedding",
                error=str(e),
                face_detection_id=face_detection_id,
                collection_id=collection_id,
                image_id=image_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to store face embedding: {str(e)}")

    async def search_faces(
        self,
        query_face: Face,
        collection_id: str,
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
                filter={"collection_id": collection_id},
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
                # Reconstruct bounding box from flattened metadata
                bounding_box = BoundingBox(
                    left=metadata["bbox_left"],
                    top=metadata["bbox_top"],
                    width=metadata["bbox_width"],
                    height=metadata["bbox_height"]
                )
                
                face = Face(
                    bounding_box=bounding_box,
                    confidence=metadata["confidence"],
                    embedding=match.values if hasattr(match, 'values') else None
                )

                matches.append(FaceMatch(
                    face=face,
                    similarity=match.score * 100,  # Convert to 0-100 scale
                    face_detection_id=metadata["face_detection_id"],
                    image_id=metadata["image_id"]
                ))

            logger.debug(
                "Face search completed",
                collection_id=collection_id,
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
                collection_id=collection_id,
                exc_info=True
            )
            raise VectorStoreError(f"Face search failed: {str(e)}")

    async def delete_face(
        self,
        image_id: str,
        collection_id: str,
    ) -> None:
        """Delete face embeddings for an image from an album."""
        try:
            # Delete all vectors with matching image_id and collection_id
            self.index.delete(
                filter={
                    "image_id": image_id,
                    "collection_id": collection_id
                }
            )

            logger.debug(
                "Deleted face embeddings",
                image_id=image_id,
                collection_id=collection_id
            )

        except Exception as e:
            logger.error(
                "Failed to delete face embeddings",
                error=str(e),
                image_id=image_id,
                collection_id=collection_id,
                exc_info=True
            )
            raise VectorStoreError(
                f"Failed to delete face embeddings: {str(e)}")

    async def delete_collection(
        self,
        collection_id: str,
    ) -> None:
        """Delete all face embeddings in an album."""
        try:
            # Delete all vectors with matching collection_id
            self.index.delete(
                filter={"collection_id": collection_id}
            )

            logger.debug(
                "Deleted collection embeddings",
                collection_id=collection_id
            )

        except Exception as e:
            logger.error(
                "Failed to delete collection",
                error=str(e),
                collection_id=collection_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to delete collection: {str(e)}")
