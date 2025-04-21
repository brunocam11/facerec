"""
Ray actor for Pinecone vector store operations to avoid serialization issues.
"""
import ray
import numpy as np
import logging
from typing import Dict, Any, Optional

from app.domain.entities.face import Face
from app.core.container import container
from app.core.logging import get_logger
from app.infrastructure.vectordb import PineconeVectorStore

logger = get_logger(__name__)

@ray.remote
class PineconeVectorStoreActor:
    """Actor that wraps PineconeVectorStore to handle serialization issues."""
    
    def __init__(self):
        """Initialize a new PineconeVectorStore instance."""
        self._vector_store: Optional[PineconeVectorStore] = None
        logger.info(f"PineconeVectorStoreActor initialized")
    
    async def initialize(self) -> None:
        """Initialize the vector store from the container."""
        self._vector_store = container.vector_store
        if not self._vector_store:
            raise RuntimeError("Vector store not initialized in container")
    
    async def store_face(self, face_dict: Dict[str, Any], collection_id: str, 
                        image_id: str, face_id: str, detection_id: str) -> bool:
        """Store a face embedding in Pinecone.
        
        Args:
            face_dict: Dictionary representation of a Face object
            collection_id: ID of the collection
            image_id: ID of the image
            face_id: ID of the face
            detection_id: ID of the detection operation
            
        Returns:
            bool: True if successful
        """
        # Reconstruct the Face object from its dict representation
        face = Face(
            bounding_box=face_dict["bounding_box"],
            confidence=face_dict["confidence"],
            embedding=np.array(face_dict["embedding"]) if face_dict["embedding"] is not None else None
        )
        
        logger.debug(f"Storing face {face_id} for image {image_id} in collection {collection_id}")
        
        if not self._vector_store:
            raise RuntimeError("Vector store not initialized")

        try:
            await self._vector_store.store_face(
                face=face,
                collection_id=collection_id,
                image_id=image_id,
                face_id=face_id,
                detection_id=detection_id
            )
            logger.debug(f"Successfully stored face {face_id} in Pinecone")
            return True
        except Exception as e:
            logger.error(
                "Failed to store face in vector store",
                error=str(e),
                collection_id=collection_id,
                image_id=image_id,
                exc_info=True
            )
            return False
        
    async def search_faces(self, query_face_dict: Dict[str, Any], 
                          collection_id: str, 
                          similarity_threshold: Optional[float] = None) -> Dict[str, Any]:
        """Search for similar faces in Pinecone.
        
        Args:
            query_face_dict: Dictionary representation of a Face object to query
            collection_id: ID of the collection to search
            similarity_threshold: Optional threshold for similarity matching
            
        Returns:
            SearchResult object containing matches
        """
        # Reconstruct the Face object from its dict representation
        query_face = Face(
            bounding_box=query_face_dict["bounding_box"],
            confidence=query_face_dict["confidence"],
            embedding=np.array(query_face_dict["embedding"]) if query_face_dict["embedding"] is not None else None
        )
        
        logger.debug(f"Searching for similar faces in collection {collection_id} "
                    f"with threshold {similarity_threshold}")
        
        if not self._vector_store:
            raise RuntimeError("Vector store not initialized")

        result = await self._vector_store.search_faces(
            query_face=query_face,
            collection_id=collection_id,
            similarity_threshold=similarity_threshold
        )
        
        logger.debug(f"Found {len(result.face_matches)} matching faces in collection {collection_id}")
        return result 