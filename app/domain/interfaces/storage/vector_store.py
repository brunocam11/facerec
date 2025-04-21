"""Vector store interface for face embeddings."""
from abc import ABC, abstractmethod
from typing import List, Optional

from ...entities.face import Face
from ...value_objects.recognition import SearchResult


class VectorStore(ABC):
    """Interface for storing and searching face embeddings."""
    
    @abstractmethod
    async def store_face(
        self,
        face: Face,
        collection_id: str,
        image_id: str,
        face_detection_id: str,
        detection_id: str = None,
    ) -> None:
        """
        Store a face embedding in a collection.
        
        Args:
            face: Face object containing embedding and metadata
            collection_id: External system collection identifier
            image_id: External system image identifier
            face_detection_id: External system face detection identifier
            detection_id: ID grouping faces from same detection operation (optional)
        
        Raises:
            VectorStoreError: If storage operation fails
        """
        pass
    
    @abstractmethod
    async def search_faces(
        self,
        query_face: Face,
        collection_id: str,
        similarity_threshold: Optional[float] = None,
        max_matches: Optional[int] = None,
    ) -> SearchResult:
        """
        Search for similar faces in a collection.
        
        Args:
            query_face: Face to search for
            collection_id: External system collection identifier
            similarity_threshold: Minimum similarity score (0-100)
            max_matches: Maximum number of matches to return
        
        Returns:
            SearchResult containing the matches found
        
        Raises:
            VectorStoreError: If search operation fails
            CollectionNotFoundError: If the specified collection doesn't exist
        """
        pass
    
    @abstractmethod
    async def delete_face(
        self,
        face_detection_id: str,
        collection_id: str,
    ) -> None:
        """
        Delete a face embedding from a collection.
        
        Args:
            face_detection_id: External system face detection identifier
            collection_id: External system collection identifier
        
        Raises:
            VectorStoreError: If deletion operation fails
            CollectionNotFoundError: If the specified collection doesn't exist
        """
        pass
    
    @abstractmethod
    async def delete_collection(
        self,
        collection_id: str,
    ) -> None:
        """
        Delete all face embeddings in a collection.
        
        Args:
            collection_id: External system collection identifier
        
        Raises:
            VectorStoreError: If deletion operation fails
            CollectionNotFoundError: If the specified collection doesn't exist
        """
        pass 