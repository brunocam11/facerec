"""Service container for dependency injection."""
from typing import Optional

from fastapi import FastAPI

from app.infrastructure.vectordb import PineconeVectorStore
from app.services import InsightFaceRecognitionService


class ServiceContainer:
    """Container for application services."""

    def __init__(self) -> None:
        """Initialize empty container."""
        self.vector_store: Optional[PineconeVectorStore] = None
        self.face_recognition_service: Optional[InsightFaceRecognitionService] = None

    async def initialize(self, app: FastAPI) -> None:
        """Initialize all services.

        Args:
            app: FastAPI application instance
        """
        # Initialize vector store
        self.vector_store = PineconeVectorStore()

        # Initialize face recognition service
        self.face_recognition_service = InsightFaceRecognitionService()

    async def cleanup(self) -> None:
        """Cleanup all services."""
        self.vector_store = None
        self.face_recognition_service = None


# Global container instance
container = ServiceContainer()
