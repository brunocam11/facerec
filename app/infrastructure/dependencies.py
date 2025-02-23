"""FastAPI dependencies."""
from typing import AsyncGenerator, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.infrastructure.storage.pinecone import PineconeVectorStore
from app.services import InsightFaceRecognitionService
from app.services.face_indexing import FaceIndexingService


async def get_session() -> AsyncSession:
    """Get database session.
    
    Returns:
        AsyncSession: Database session
    """
    async with get_db_session() as session:
        yield session


async def get_uow(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> UnitOfWork:
    """Get unit of work.
    
    Args:
        session: Database session
        
    Returns:
        UnitOfWork: Unit of work instance
    """
    return UnitOfWork(session)


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