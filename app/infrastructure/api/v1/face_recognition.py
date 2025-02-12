"""Face recognition API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, Query, Path
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.domain.entities.face import Face, BoundingBox
from app.domain.value_objects.recognition import (
    DetectionResult,
    SearchResult,
    FaceMatch
)
from app.services import InsightFaceRecognitionService
from app.infrastructure.storage.pinecone import PineconeVectorStore

logger = get_logger(__name__)
router = APIRouter()


class FaceRecord(BaseModel):
    """Face record returned by face operations."""
    face_id: UUID = Field(..., description="Unique identifier of the detected face")
    bounding_box: BoundingBox = Field(..., description="Face location in image")
    confidence: float = Field(..., description="Confidence score (0-100)")
    external_image_id: str = Field(None, description="External image reference")


class DetectionResponse(BaseModel):
    """Response model for face detection endpoint."""
    face_records: List[FaceRecord] = Field(..., description="List of detected faces")


class IndexFacesRequest(BaseModel):
    """Request model for indexing faces."""
    external_image_id: str = Field(None, description="External image reference")
    max_faces: int = Field(20, description="Maximum number of faces to index")


class SearchFacesResponse(BaseModel):
    """Response model for face search endpoint."""
    searched_face_id: UUID = Field(..., description="ID of the face used for search")
    face_matches: List[FaceMatch] = Field(..., description="Similar faces found") 