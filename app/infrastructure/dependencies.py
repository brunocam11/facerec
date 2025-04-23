"""FastAPI dependency providers."""
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends

from app.core.container import ServiceContainer, container
from app.core.exceptions import ServiceNotInitializedError
from app.infrastructure.vectordb import PineconeVectorStore
from app.services import InsightFaceRecognitionService
from app.services.aws.s3 import S3Service
from app.services.face_indexing import FaceIndexingService
from app.services.face_matching import FaceMatchingService


async def get_container() -> ServiceContainer:
    """Dependency provider for the global ServiceContainer instance."""
    if not container.sqs_service:  # Check a core service for initialization
        # Attempt to initialize if not already done (e.g., during testing)
        try:
            await container.initialize()
        except Exception as e:
            # Raise specific error if container is needed but fails init
            raise ServiceNotInitializedError(f"Service container could not be initialized: {e}")
    return container


async def get_face_recognition_service() -> AsyncGenerator[InsightFaceRecognitionService, None]:
    """Provide the initialized InsightFace service.

    Yields:
        InsightFaceRecognitionService: Initialized face recognition service

    Raises:
        ServiceNotInitializedError: If service is not initialized
    """
    cont = await get_container()
    if cont.face_recognition_service is None:
        raise ServiceNotInitializedError(
            "Face recognition service not initialized")
    yield cont.face_recognition_service


async def get_vector_store() -> AsyncGenerator[PineconeVectorStore, None]:
    """Provide the initialized Pinecone vector store.

    Yields:
        PineconeVectorStore: Initialized vector store instance

    Raises:
        ServiceNotInitializedError: If vector store is not initialized
    """
    cont = await get_container()
    if cont.vector_store is None:
        raise ServiceNotInitializedError("Vector store not initialized")
    yield cont.vector_store


async def get_s3_service() -> AsyncGenerator[S3Service, None]:
    """Provide the initialized S3 storage service.

    Yields:
        S3Service: Initialized S3 storage service

    Raises:
        ServiceNotInitializedError: If S3 storage service is not initialized
    """
    cont = await get_container()
    if cont.s3_service is None:
        raise ServiceNotInitializedError("S3 storage service not initialized")
    yield cont.s3_service


async def get_face_indexing_service(container: ServiceContainer = Depends(get_container)) -> AsyncGenerator[FaceIndexingService, None]:
    """Dependency provider for FaceIndexingService."""
    if not container.face_indexing_service:
        raise ServiceNotInitializedError("FaceIndexingService not found in initialized container")
    yield container.face_indexing_service


async def get_face_matching_service(
    face_service: InsightFaceRecognitionService = Depends(
        get_face_recognition_service),
    vector_store: PineconeVectorStore = Depends(get_vector_store),
    storage: S3Service = Depends(get_s3_service),
) -> AsyncGenerator[FaceMatchingService, None]:
    """Provide the face matching service.

    Args:
        face_service: Face recognition service instance
        vector_store: Vector store instance
        storage: S3 storage service instance

    Yields:
        FaceMatchingService: Initialized matching service
    """
    service = FaceMatchingService(
        face_service=face_service,
        vector_store=vector_store,
        s3_service=storage,
    )
    yield service
