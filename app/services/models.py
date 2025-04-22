"""Service-specific models.

This module contains models used by services that are independent of the API layer.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.domain.entities.face import Face, BoundingBox


class ServiceFaceRecord(BaseModel):
    """Face record used within services.
    
    This model represents face data for internal service operations.
    """
    face_id: str = Field(..., description="Unique identifier for the face")
    bounding_box: BoundingBox = Field(..., description="Face bounding box coordinates")
    confidence: float = Field(..., description="Face detection confidence score", ge=0.0, le=1.0)
    image_key: str = Field(..., description="S3 object key (path) of the source image")
    created_at: datetime = Field(..., description="Timestamp when the face was processed/stored")
    
    @classmethod
    def from_face(cls, face: Face, face_id: str, image_key: str) -> "ServiceFaceRecord":
        """Create a face record from a Face entity.
        
        Args:
            face: Face entity (should include created_at and face_id)
            face_id: Unique identifier for the face (override if needed)
            image_key: S3 object key (path) of the source image
            
        Returns:
            ServiceFaceRecord: Face record
        """
        record_face_id = face_id or getattr(face, 'face_id', None)
        if record_face_id is None:
            raise ValueError("Face ID is required to create a ServiceFaceRecord")

        created_at_ts = getattr(face, 'created_at', None) or datetime.now()

        return cls(
            face_id=record_face_id,
            bounding_box=face.bounding_box,
            confidence=face.confidence,
            image_key=image_key,
            created_at=created_at_ts
        )


class ServiceIndexFacesResponse(BaseModel):
    """Response model for face indexing service.
    
    This model represents the result of indexing faces within the service layer.
    """
    face_records: List[ServiceFaceRecord] = Field(..., description="List of indexed face records")
    detection_id: str = Field(..., description="Unique identifier for the detection operation")
    image_key: str = Field(..., description="S3 object key (path) of the source image")


class ServiceFaceMatch(BaseModel):
    """Service model for a face match."""
    face_id: str = Field(..., description="Unique identifier for the matched face")
    similarity: float = Field(..., description="Similarity score (0.0 to 1.0)", ge=0.0, le=1.0)
    image_key: str = Field(..., description="S3 object key (path) of the source image")


class ServiceSearchResult(BaseModel):
    """Service response model for face search results."""
    searched_face_id: str = Field(..., description="Unique identifier for the searched face")
    face_matches: List[ServiceFaceMatch] = Field(..., description="List of matching faces") 