"""Vector store interface for face embeddings."""
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ...entities.face import Face
from ...value_objects.recognition import SearchResult


class VectorStore(ABC):
    """Interface for storing and searching face embeddings."""
    
    @abstractmethod
    async def store_face(
        self,
        face: Face,
        collection_id: UUID,
        image_id: UUID,
        face_detection_id: UUID,
    ) -> None:
        """
        Store a face embedding in a collection.
        
        Args:
            face: Face object containing embedding and metadata
            collection_id: ID of the collection to store in
            image_id: External image ID reference
            face_detection_id: ID of the face detection record
        
        Raises:
            VectorStoreError: If storage operation fails
        """
        pass
    
    @abstractmethod
    async def search_faces(
        self,
        query_face: Face,
        collection_id: UUID,
        similarity_threshold: Optional[float] = None,
        max_matches: Optional[int] = None,
    ) -> SearchResult:
        """
        Search for similar faces in a collection.
        
        Args:
            query_face: Face to search for
            collection_id: ID of the collection to search in
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
        face_detection_id: UUID,
        collection_id: UUID,
    ) -> None:
        """
        Delete a face embedding from a collection.
        
        Args:
            face_detection_id: ID of the face detection to delete
            collection_id: ID of the collection containing the face
        
        Raises:
            VectorStoreError: If deletion operation fails
            CollectionNotFoundError: If the specified collection doesn't exist
        """
        pass
    
    @abstractmethod
    async def delete_collection(
        self,
        collection_id: UUID,
    ) -> None:
        """
        Delete all face embeddings in a collection.
        
        Args:
            collection_id: ID of the collection to delete
        
        Raises:
            VectorStoreError: If deletion operation fails
            CollectionNotFoundError: If the specified collection doesn't exist
        """
        pass 