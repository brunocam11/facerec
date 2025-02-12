"""Face recognition service interface."""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ...entities.face import Face
from ...value_objects.recognition import DetectionResult, ComparisonResult, SearchResult


class FaceRecognitionService(ABC):
    """Interface for face recognition operations."""
    
    @abstractmethod
    async def detect_faces(
        self,
        image_bytes: bytes,
        max_faces: Optional[int] = None,
        min_confidence: Optional[float] = None,
    ) -> DetectionResult:
        """
        Detect faces in the provided image.
        
        Args:
            image_bytes: Raw image data
            max_faces: Maximum number of faces to detect (None for no limit)
            min_confidence: Minimum confidence threshold (0-100)
        
        Returns:
            DetectionResult containing the detected faces
        
        Raises:
            InvalidImageError: If the image format is invalid
            ImageTooLargeError: If the image size exceeds limits
        """
        pass
    
    @abstractmethod
    async def extract_embeddings(
        self,
        image_bytes: bytes,
        max_faces: Optional[int] = None,
    ) -> List[Face]:
        """
        Extract face embeddings from an image.
        
        Args:
            image_bytes: Raw image data
            max_faces: Maximum number of faces to detect (None for no limit)
        
        Returns:
            List of Face objects with embeddings computed
        
        Raises:
            InvalidImageError: If the image format is invalid
            ImageTooLargeError: If the image size exceeds limits
            NoFaceDetectedError: If no face is found in the image
        """
        pass

    @abstractmethod
    async def compare_faces(
        self,
        source_image: bytes,
        target_image: bytes,
        similarity_threshold: Optional[float] = None,
    ) -> ComparisonResult:
        """
        Compare faces between two images.
        
        Args:
            source_image: Raw image data of the source face
            target_image: Raw image data of the target face
            similarity_threshold: Minimum similarity score (0-100)
        
        Returns:
            ComparisonResult containing the comparison details
        
        Raises:
            InvalidImageError: If any image format is invalid
            ImageTooLargeError: If any image size exceeds limits
            NoFaceDetectedError: If no face is found in either image
            MultipleFacesError: If multiple faces found in either image
        """
        pass
    
    @abstractmethod
    async def search_faces(
        self,
        image: bytes,
        face_embeddings: List[List[float]],
        similarity_threshold: Optional[float] = None,
        max_matches: Optional[int] = None,
    ) -> SearchResult:
        """
        Search for similar faces using face embeddings.
        
        Args:
            image: Raw image data to search for
            face_embeddings: List of face embeddings to search against
            similarity_threshold: Minimum similarity score (0-100)
            max_matches: Maximum number of matches to return
        
        Returns:
            SearchResult containing the search matches
        
        Raises:
            InvalidImageError: If the image format is invalid
            ImageTooLargeError: If the image size exceeds limits
            NoFaceDetectedError: If no face is found in the image
            MultipleFacesError: If multiple faces found in the image
        """
        pass 