"""FastAPI dependencies."""
from typing import Annotated

from fastapi import Depends

from app.infrastructure.vectordb import PineconeVectorStore
from app.services import InsightFaceRecognitionService
from app.services.face_indexing import FaceIndexingService


def get_vector_store() -> PineconeVectorStore:
    """Get vector store instance.

    Returns:
        PineconeVectorStore: Vector store for face embeddings
    """
    return PineconeVectorStore()


def get_face_service() -> InsightFaceRecognitionService:
    """Get face recognition service instance.

    Returns:
        InsightFaceRecognitionService: Face recognition service
    """
    return InsightFaceRecognitionService()


def get_indexing_service(
    face_service: Annotated[InsightFaceRecognitionService, Depends(get_face_service)],
    vector_store: Annotated[PineconeVectorStore, Depends(get_vector_store)]
) -> FaceIndexingService:
    """Get face indexing service instance.

    Args:
        face_service: Face recognition service
        vector_store: Vector store for embeddings

    Returns:
        FaceIndexingService: Face indexing service
    """
    return FaceIndexingService(
        face_service=face_service,
        vector_store=vector_store
    )
