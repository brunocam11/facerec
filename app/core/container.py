"""Service container for dependency injection."""
from typing import Optional

# Import interfaces
from app.domain.interfaces.storage.vector_store import VectorStore
from app.domain.interfaces.recognition.face_recognition import FaceRecognitionService

# Import concrete implementations used for instantiation
from app.infrastructure.vectordb import PineconeVectorStore
from app.services.aws.s3 import S3Service
from app.services.aws.sqs import SQSService
from app.services.face_indexing import FaceIndexingService
from app.services.face_matching import FaceMatchingService
from app.services.recognition.insight_face import InsightFaceRecognitionService


class ServiceContainer:
    """Container for application services.

    This container manages the lifecycle and dependencies of all services in the application.
    It ensures proper initialization order and provides a single source of truth for service instances.

    Example:
        ```python
        container = ServiceContainer()
        await container.initialize()

        # Get services from container
        face_indexing = container.face_indexing_service
        face_matching = container.face_matching_service
        ```
    """

    def __init__(self) -> None:
        """Initialize empty container."""
        # Core services - Use interface type hints
        self.vector_store: Optional[VectorStore] = None
        self.face_recognition_service: Optional[FaceRecognitionService] = None
        self.s3_service: Optional[S3Service] = None
        self.sqs_service: Optional[SQSService] = None

        # Domain services (depend on interfaces)
        self.face_indexing_service: Optional[FaceIndexingService] = None
        self.face_matching_service: Optional[FaceMatchingService] = None

    async def initialize(self) -> None:
        """Initialize all services in the correct order."""
        # Instantiate concrete implementations
        self.vector_store = PineconeVectorStore()
        self.s3_service = S3Service()
        self.sqs_service = SQSService()
        await self.sqs_service.initialize()
        self.face_recognition_service = InsightFaceRecognitionService()
        self.face_indexing_service = FaceIndexingService(
            recognition_service=self.face_recognition_service,
            vector_store=self.vector_store,
            s3_service=self.s3_service
        )
        self.face_matching_service = FaceMatchingService(
            face_service=self.face_recognition_service,
            vector_store=self.vector_store,
            s3_service=self.s3_service
        )

    async def cleanup(self) -> None:
        """Cleanup all services in reverse order of initialization."""
        # Cleanup domain services
        self.face_indexing_service = None
        self.face_matching_service = None

        # Cleanup core services
        self.face_recognition_service = None

        # Cleanup AWS services
        if self.sqs_service:
            await self.sqs_service.cleanup()
            self.sqs_service = None

        # S3Service cleanup is handled by its internal context manager
        # if self.s3_service:
        #     await self.s3_service.cleanup() # REMOVED
        #     self.s3_service = None
        self.s3_service = None # Still nullify the reference

        # Cleanup infrastructure services
        self.vector_store = None


# Global container instance
container = ServiceContainer()
