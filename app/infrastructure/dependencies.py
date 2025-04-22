"""FastAPI dependency providers."""
from typing import AsyncGenerator

from fastapi import Depends

from app.core.container import container
from app.core.exceptions import ServiceNotInitializedError
from app.infrastructure.vectordb import PineconeVectorStore
from app.services import InsightFaceRecognitionService
from app.services.aws.s3 import S3Service
from app.services.face_indexing import FaceIndexingService
from app.services.face_matching import FaceMatchingService


async def get_face_recognition_service() -> AsyncGenerator[InsightFaceRecognitionService, None]:
    """Provide the initialized InsightFace service.

    Yields:
        InsightFaceRecognitionService: Initialized face recognition service

    Raises:
        ServiceNotInitializedError: If service is not initialized
    """
    if container.face_recognition_service is None:
        raise ServiceNotInitializedError(
            "Face recognition service not initialized")
    yield container.face_recognition_service


async def get_vector_store() -> AsyncGenerator[PineconeVectorStore, None]:
    """Provide the initialized Pinecone vector store.

    Yields:
        PineconeVectorStore: Initialized vector store instance

    Raises:
        ServiceNotInitializedError: If vector store is not initialized
    """
    if container.vector_store is None:
        raise ServiceNotInitializedError("Vector store not initialized")
    yield container.vector_store


async def get_s3_service() -> AsyncGenerator[S3Service, None]:
    """Provide the initialized S3 storage service.

    Yields:
        S3Service: Initialized S3 storage service

    Raises:
        ServiceNotInitializedError: If S3 storage service is not initialized
    """
    if container.s3_service is None:
        raise ServiceNotInitializedError("S3 storage service not initialized")
    yield container.s3_service


async def get_face_indexing_service(
    face_service: InsightFaceRecognitionService = Depends(
        get_face_recognition_service),
    vector_store: PineconeVectorStore = Depends(get_vector_store),
    storage: S3Service = Depends(get_s3_service),
) -> AsyncGenerator[FaceIndexingService, None]:
    """Provide the face indexing service.

    Args:
        face_service: Face recognition service instance
        vector_store: Vector store instance
        storage: S3 storage service instance

    Yields:
        FaceIndexingService: Initialized indexing service
    """
    service = FaceIndexingService(
        face_service=face_service,
        vector_store=vector_store,
        storage=storage,
    )
    yield service


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
