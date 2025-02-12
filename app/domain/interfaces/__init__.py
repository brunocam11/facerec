"""Service interfaces package."""
from .recognition import FaceRecognitionService
from .storage import VectorStore

__all__ = ["FaceRecognitionService", "VectorStore"] 