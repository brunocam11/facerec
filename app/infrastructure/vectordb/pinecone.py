"""Pinecone implementation of vector store for face embeddings."""
from typing import List, Optional
from datetime import datetime
import uuid

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
        face_id: str,
        detection_id: str,
    ) -> None:
        """Store a face embedding in a collection namespace.
        
        This implementation stores face embeddings in Pinecone using ANN with cosine similarity.
        The face embedding should be normalized for optimal cosine similarity performance.
        
        Args:
            face: Face object with embedding vector
            collection_id: Collection namespace in Pinecone
            image_id: Original image identifier
            face_id: Unique identifier for this face
            detection_id: ID grouping all faces detected in same operation
            
        Raises:
            VectorStoreError: If storage operation fails
        """
        try:
            # Use face_id as vector ID for direct lookups
            vector_id = face_id

            # Get current timestamp
            now = datetime.now().isoformat()

            # Prepare metadata (no need to store collection_id since it's in namespace)
            metadata = PineconeMetadata(
                face_id=face_id,
                image_id=image_id,
                detection_id=detection_id,
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
                face_id=face_id,
                detection_id=detection_id,
                collection_id=collection_id,
                image_id=image_id,
                created_at=now
            )

        except Exception as e:
            logger.error(
                "Failed to store face embedding",
                error=str(e),
                face_id=face_id,
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
        """Retrieve face records for a given image ID from a collection namespace."""
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
                        created_at=created_at,
                    ))
                except Exception as e:
                    logger.error(
                        "Failed to convert face record",
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
            raise VectorStoreError(f"Failed to retrieve faces: {str(e)}")

    async def search_faces(
        self,
        query_face: Face,
        collection_id: str,
        similarity_threshold: Optional[float] = None,
    ) -> SearchResult:
        """Search for similar faces in a collection namespace.
        
        This implementation uses Pinecone's ANN search with cosine similarity.
        Cosine similarity scores from Pinecone range from -1 to 1, where:
        - 1 means vectors are identical
        - 0 means vectors are orthogonal (unrelated)
        - -1 means vectors are opposite
        
        We transform these scores to a 0-100 scale for better usability:
        - 100 means perfect match (cosine similarity of 1)
        - 50 means unrelated (cosine similarity of 0)
        - 0 means opposite (cosine similarity of -1)
        
        Args:
            query_face: Face to search for
            collection_id: Collection namespace in Pinecone
            similarity_threshold: Minimum similarity threshold (0-1 scale)
            max_matches: Maximum number of matches to return
            
        Returns:
            SearchResult with face matches and their similarity scores (0-100)
            
        Raises:
            VectorStoreError: If search operation fails
        """
        try:
            # Set defaults from settings
            threshold = similarity_threshold or settings.SIMILARITY_THRESHOLD

            # Ensure query embedding is normalized for optimal cosine similarity
            if query_face.embedding is None:
                raise VectorStoreError("Query face has no embedding")
                
            # Normalize the query embedding vector for better cosine similarity results
            query_embedding = query_face.embedding
            norm = np.linalg.norm(query_embedding)
            if norm > 0:
                normalized_query = query_embedding / norm
            else:
                normalized_query = query_embedding

            # Query Pinecone in the collection namespace
            results = self.index.query(
                vector=normalized_query.tolist(),
                namespace=collection_id,
                top_k=100,
                include_metadata=True,
                include_values=True
            )

            # Convert results to domain model
            matches = []
            for match in results.matches:
                # Transform cosine similarity from [-1, 1] to [0, 100]
                similarity_score = transform_cosine_similarity(match.score)
                
                # Skip results below threshold
                if similarity_score < threshold * 100:  # Convert threshold to same scale
                    continue

                metadata = match.metadata
                # Reconstruct bounding box from metadata
                bounding_box = BoundingBox(
                    left=metadata["bbox_left"],
                    top=metadata["bbox_top"],
                    width=metadata["bbox_width"],
                    height=metadata["bbox_height"]
                )

                # Convert embedding to numpy array if it exists, otherwise use None
                embedding = np.array(match.values) if hasattr(match, 'values') and match.values else None

                face = Face(
                    bounding_box=bounding_box,
                    confidence=metadata["confidence"],
                    embedding=embedding
                )

                matches.append(FaceMatch(
                    face_id=metadata["face_id"],
                    similarity=similarity_score,  # Use transformed score
                    image_id=metadata["image_id"]
                ))

            logger.debug(
                "Face search completed",
                collection_id=collection_id,
                matches_found=len(matches),
                threshold=threshold
            )

            # Generate a unique ID for the searched face
            searched_face_id = str(uuid.uuid4())

            return SearchResult(
                searched_face_id=searched_face_id,
                face_matches=matches
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
        """Delete face embeddings for an image from a collection namespace."""
        try:
            # Delete all vectors with matching image_id in the namespace
            self.index.delete(
                filter={"image_id": image_id},
                namespace=collection_id
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
            raise VectorStoreError(f"Failed to delete face embeddings: {str(e)}")

    async def delete_collection(
        self,
        collection_id: str,
    ) -> None:
        """Delete all face embeddings in a collection namespace."""
        try:
            # Delete the entire namespace
            self.index.delete(
                delete_all=True,
                namespace=collection_id
            )

            logger.debug(
                "Deleted collection namespace",
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
