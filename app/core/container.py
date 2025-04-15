"""Service container for dependency injection."""
from typing import Optional

from fastapi import FastAPI

from app.infrastructure.vectordb import PineconeVectorStore
from app.services import InsightFaceRecognitionService
from app.services.aws.sqs import SQSService
from app.services.aws.s3 import S3Service


class ServiceContainer:
    """Container for application services."""

    def __init__(self) -> None:
        """Initialize empty container."""
        self.vector_store: Optional[PineconeVectorStore] = None
        self.face_recognition_service: Optional[InsightFaceRecognitionService] = None
        self.sqs_service: Optional[SQSService] = None
        self.s3_service: Optional[S3Service] = None

    async def initialize(self, app: FastAPI) -> None:
        """Initialize all services.

        Args:
            app: FastAPI application instance
        """
        # Initialize vector store
        self.vector_store = PineconeVectorStore()

        # Initialize face recognition service
        self.face_recognition_service = InsightFaceRecognitionService()
        
        # Initialize AWS services
        self.sqs_service = SQSService()
        await self.sqs_service.initialize()
        
        self.s3_service = S3Service()
        await self.s3_service.initialize()

    async def cleanup(self) -> None:
        """Cleanup all services."""
        if self.sqs_service:
            await self.sqs_service.cleanup()
        
        if self.s3_service:
            await self.s3_service.cleanup()
            
        self.vector_store = None
        self.face_recognition_service = None
        self.sqs_service = None
        self.s3_service = None


# Global container instance
container = ServiceContainer()
