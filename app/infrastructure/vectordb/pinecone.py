"""Pinecone implementation of vector store for face embeddings."""
from typing import List, Optional
from datetime import datetime

import numpy as np
from pinecone import Pinecone
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger
from app.domain.entities.face import BoundingBox, Face
from app.domain.interfaces.storage.vector_store import VectorStore
from app.domain.value_objects.recognition import FaceMatch, SearchResult
from app.infrastructure.vectordb.models import VectorFaceRecord

logger = get_logger(__name__)


def transform_cosine_similarity(cosine_score: float) -> float:
    """Transform cosine similarity from [-1, 1] to [0, 100] scale.
    
    Args:
        cosine_score: Cosine similarity score from Pinecone (-1 to 1)
        
    Returns:
        Transformed score on 0-100 scale
    """
    # Transform from [-1, 1] to [0, 1]
    normalized_score = (cosine_score + 1) / 2
    # Scale to [0, 100]
    return normalized_score * 100


class PineconeMetadata(BaseModel):
    """Metadata stored with face vectors in Pinecone.
    
    Note: collection_id is handled via Pinecone namespaces and not stored in metadata.
    
    Attributes:
        face_id: Unique identifier for this face
        image_id: Original image identifier
        detection_id: ID grouping all faces detected in same operation
        confidence: Detection confidence score
        bbox_*: Bounding box coordinates normalized to 0-1 range
        created_at: ISO format timestamp of when this face was indexed
    """
    face_id: str = Field(
        description="Unique identifier for this face"
    )
    image_id: str = Field(
        description="Original image identifier"
    )
    detection_id: str = Field(
        description="ID grouping faces from same detection operation"
    )
    confidence: float = Field(
        description="Detection confidence score"
    )
    bbox_left: float = Field(
        description="Left coordinate of the face bounding box"
    )
    bbox_top: float = Field(
        description="Top coordinate of the face bounding box"
    )
    bbox_width: float = Field(
        description="Width of the face bounding box"
    )
    bbox_height: float = Field(
        description="Height of the face bounding box"
    )
    created_at: str = Field(
        description="ISO format timestamp of when this face was indexed"
    )


class PineconeVectorStore(VectorStore):
    """Pinecone implementation of vector store for face embeddings."""

    def __init__(self) -> None:
        """Initialize Pinecone client and index.
        
        Raises:
            VectorStoreError: If initialization fails
        """
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
        detection_id: str = None,
    ) -> None:
        """Store a face embedding in a collection namespace.
        
        This implementation stores face embeddings in Pinecone using ANN with cosine similarity.
        The face embedding should be normalized for optimal cosine similarity performance.
        
        Args:
            face: Face object with embedding vector
            collection_id: Collection namespace in Pinecone
            image_id: Original image identifier
            face_detection_id: External system face detection identifier
            detection_id: ID grouping faces from same detection operation (optional)
            
        Raises:
            VectorStoreError: If storage operation fails
        """
        try:
            # Use face_detection_id as vector ID for direct lookups
            vector_id = face_detection_id

            # Get current timestamp
            now = datetime.now().isoformat()

            # Use provided detection_id or fallback to face_detection_id if not provided
            group_detection_id = detection_id if detection_id else face_detection_id

            # Prepare metadata (no need to store collection_id since it's in namespace)
            metadata = PineconeMetadata(
                face_id=face_detection_id,
                image_id=image_id,
                detection_id=group_detection_id,
                confidence=face.confidence,
                bbox_left=face.bounding_box.left,
                bbox_top=face.bounding_box.top,
                bbox_width=face.bounding_box.width,
                bbox_height=face.bounding_box.height,
                created_at=now
            )

            # Ensure embedding is normalized for optimal cosine similarity
            embedding = face.embedding
            if embedding is not None:
                # Normalize the embedding vector for better cosine similarity results
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    normalized_embedding = embedding / norm
                else:
                    normalized_embedding = embedding
                
                # Upsert the embedding with metadata in the collection namespace
                self.index.upsert(
                    vectors=[(
                        vector_id,
                        normalized_embedding.tolist(),  # Use normalized embedding
                        metadata.dict()
                    )],
                    namespace=collection_id  # Use collection_id as namespace
                )
            else:
                raise VectorStoreError("Face embedding is None, cannot store in vector database")

            logger.debug(
                "Stored face embedding",
                face_id=face_detection_id,
                detection_id=group_detection_id,
                collection_id=collection_id,
                image_id=image_id,
                created_at=now
            )

        except Exception as e:
            logger.error(
                "Failed to store face embedding",
                error=str(e),
                face_id=face_detection_id,
                collection_id=collection_id,
                image_id=image_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to store face embedding: {str(e)}")

    async def get_faces_by_image_id(
        self,
        image_id: str,
        collection_id: str,
    ) -> tuple[List[VectorFaceRecord], Optional[str]]:
        """Retrieve face records for a given image ID from a collection namespace.
        
        Args:
            image_id: Original image identifier
            collection_id: Collection namespace in Pinecone
            
        Returns:
            Tuple of (list of face records, detection_id)
            
        Raises:
            VectorStoreError: If retrieval operation fails
        """
        try:
            # Query Pinecone in the collection namespace
            response = self.index.query(
                vector=[0] * 512,  # Dummy vector since we're filtering by metadata
                filter={
                    "image_id": image_id
                },
                namespace=collection_id,
                include_metadata=True,
                include_values=True,
                top_k=100
            )

            if not response or not response.matches:
                logger.debug(
                    "No faces found for image",
                    image_id=image_id,
                    collection_id=collection_id
                )
                return [], None

            # Get detection_id from first match
            detection_id = None
            for match in response.matches:
                if match.metadata:
                    detection_id = match.metadata.get("detection_id")
                    if detection_id:
                        break

            if not detection_id:
                logger.warning(
                    "No detection_id found in metadata",
                    image_id=image_id,
                    collection_id=collection_id
                )
                return [], None

            # Convert Pinecone records to vector records
            records = []
            for match in response.matches:
                if not match.metadata or not match.values:
                    logger.warning(
                        "Missing metadata or vector values for face record",
                        face_id=match.id,
                        collection_id=collection_id
                    )
                    continue

                try:
                    # Parse timestamps from ISO format
                    created_at = datetime.fromisoformat(match.metadata.get("created_at", datetime.now().isoformat()))

                    records.append(VectorFaceRecord(
                        face_id=match.id,
                        collection_id=collection_id,
                        external_image_id=image_id,
                        detection_id=match.metadata.get("detection_id"),
                        confidence=float(match.metadata.get("confidence", 0)),
                        embedding=np.array(match.values),
                        bbox_left=float(match.metadata.get("bbox_left", 0)),
                        bbox_top=float(match.metadata.get("bbox_top", 0)),
                        bbox_width=float(match.metadata.get("bbox_width", 0)),
                        bbox_height=float(match.metadata.get("bbox_height", 0)),
                        created_at=created_at
                    ))
                except Exception as e:
                    logger.error(
                        "Failed to parse face record",
                        error=str(e),
                        face_id=match.id,
                        collection_id=collection_id,
                        exc_info=True
                    )
                    continue

            return records, detection_id

        except Exception as e:
            logger.error(
                "Failed to retrieve faces by image ID",
                error=str(e),
                image_id=image_id,
                collection_id=collection_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to retrieve faces by image ID: {str(e)}")

    async def search_faces(
        self,
        query_face: Face,
        collection_id: str,
        similarity_threshold: Optional[float] = None,
        max_matches: Optional[int] = None,
    ) -> SearchResult:
        """Search for similar faces in a collection.
        
        Args:
            query_face: Face to search for
            collection_id: Collection namespace in Pinecone
            similarity_threshold: Minimum similarity score (0-100)
            max_matches: Maximum number of matches to return
            
        Returns:
            SearchResult containing the matches found
            
        Raises:
            VectorStoreError: If search operation fails
        """
        try:
            # Normalize query embedding
            query_embedding = query_face.embedding
            if query_embedding is None:
                raise VectorStoreError("Query face has no embedding")

            norm = np.linalg.norm(query_embedding)
            if norm > 0:
                normalized_embedding = query_embedding / norm
            else:
                normalized_embedding = query_embedding

            # Convert similarity threshold from [0, 100] to [-1, 1]
            if similarity_threshold is not None:
                # Transform from [0, 100] to [0, 1]
                normalized_threshold = similarity_threshold / 100
                # Transform from [0, 1] to [-1, 1]
                cosine_threshold = (normalized_threshold * 2) - 1
            else:
                cosine_threshold = None

            # Default max_matches to 100 if not specified
            top_k = max_matches if max_matches is not None else 100

            # Search in Pinecone
            response = self.index.query(
                vector=normalized_embedding.tolist(),
                namespace=collection_id,
                include_metadata=True,
                include_values=True,
                top_k=top_k,
                filter=None  # No metadata filtering for search
            )

            if not response or not response.matches:
                logger.debug(
                    "No matches found",
                    collection_id=collection_id,
                    threshold=similarity_threshold
                )
                return SearchResult(searched_face_id="", face_matches=[])

            # Convert matches to FaceMatch objects
            face_matches = []
            for match in response.matches:
                if not match.metadata or not match.values:
                    logger.warning(
                        "Missing metadata or vector values for match",
                        face_id=match.id,
                        collection_id=collection_id
                    )
                    continue

                try:
                    # Transform cosine similarity to [0, 100] scale
                    similarity = transform_cosine_similarity(match.score)

                    # Skip if below threshold
                    if similarity_threshold is not None and similarity < similarity_threshold:
                        continue

                    face_matches.append(FaceMatch(
                        face_id=match.id,
                        similarity=similarity,
                        bounding_box=BoundingBox(
                            left=float(match.metadata.get("bbox_left", 0)),
                            top=float(match.metadata.get("bbox_top", 0)),
                            width=float(match.metadata.get("bbox_width", 0)),
                            height=float(match.metadata.get("bbox_height", 0))
                        )
                    ))
                except Exception as e:
                    logger.error(
                        "Failed to parse face match",
                        error=str(e),
                        face_id=match.id,
                        collection_id=collection_id,
                        exc_info=True
                    )
                    continue

            return SearchResult(
                searched_face_id=query_face.face_id,
                face_matches=face_matches
            )

        except Exception as e:
            logger.error(
                "Failed to search faces",
                error=str(e),
                collection_id=collection_id,
                threshold=similarity_threshold,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to search faces: {str(e)}")

    async def delete_face(
        self,
        face_detection_id: str,
        collection_id: str,
    ) -> None:
        """Delete a face embedding from a collection.
        
        Args:
            face_detection_id: External system face detection identifier
            collection_id: Collection namespace in Pinecone
            
        Raises:
            VectorStoreError: If deletion operation fails
        """
        try:
            # Delete the face by ID
            self.index.delete(
                ids=[face_detection_id],
                namespace=collection_id
            )

            logger.info(
                "Deleted face",
                face_detection_id=face_detection_id,
                collection_id=collection_id
            )

        except Exception as e:
            logger.error(
                "Failed to delete face",
                error=str(e),
                face_detection_id=face_detection_id,
                collection_id=collection_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to delete face: {str(e)}")

    async def delete_collection(
        self,
        collection_id: str,
    ) -> None:
        """Delete all face embeddings in a collection.
        
        Args:
            collection_id: Collection namespace in Pinecone
            
        Raises:
            VectorStoreError: If deletion operation fails
        """
        try:
            # Delete all vectors in the namespace
            self.index.delete(
                delete_all=True,
                namespace=collection_id
            )

            logger.info(
                "Deleted collection",
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
