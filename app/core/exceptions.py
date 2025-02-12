"""Custom exceptions for face recognition service."""
from typing import Optional


class FaceRecognitionError(Exception):
    """Base exception for face recognition operations."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        """
        Initialize face recognition error.
        
        Args:
            message: Error description
            details: Additional error context
        """
        super().__init__(message)
        self.details = details or {}


class InvalidImageError(FaceRecognitionError):
    """Raised when the provided image is invalid or cannot be processed."""
    pass


class ImageTooLargeError(FaceRecognitionError):
    """Raised when the image dimensions exceed the maximum allowed size."""
    pass


class NoFaceDetectedError(FaceRecognitionError):
    """Raised when no face is detected in the image."""
    pass


class MultipleFacesError(FaceRecognitionError):
    """Raised when multiple faces are found in an image that expects only one face."""
    pass


class ModelLoadError(FaceRecognitionError):
    """Raised when the face recognition model fails to load."""
    pass


class VectorStoreError(FaceRecognitionError):
    """Base exception for vector store operations."""
    pass


class CollectionNotFoundError(VectorStoreError):
    """Raised when attempting to access a non-existent collection."""
    pass 