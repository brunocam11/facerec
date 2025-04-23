"""Face recognition service interface."""
from abc import ABC, abstractmethod
from typing import List, Optional

from ...entities.face import Face
from ...value_objects.recognition import DetectionResult


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
            min_confidence: Minimum confidence threshold (0-1, implementation handles scale)

        Returns:
            DetectionResult containing the detected faces (domain Face objects)

        Raises:
            InvalidImageError: If the image format is invalid
            ImageTooLargeError: If the image size exceeds limits
        """
        pass

    @abstractmethod
    async def get_faces_with_embeddings(
        self,
        image_bytes: bytes,
        max_faces: Optional[int] = None,
    ) -> List[Face]:
        """
        Detect faces and extract their embeddings.

        Args:
            image_bytes: Raw image data
            max_faces: Maximum number of faces to detect (None for no limit)

        Returns:
            List of domain Face objects, each containing confidence, bbox, and embedding.
            Returns an empty list if no faces are detected that meet internal criteria.

        Raises:
            InvalidImageError: If the image format is invalid
            ImageTooLargeError: If the image size exceeds limits
            # Note: Implementation might raise NoFaceDetectedError internally,
            # but callers often check for empty list instead.
            # Let's keep NoFaceDetectedError out of interface signature for flexibility.
        """
        pass
