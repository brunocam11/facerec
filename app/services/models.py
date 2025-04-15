"""Service-specific models.

This module contains models used by services that are independent of the API layer.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

from app.domain.entities.face import Face, BoundingBox


class ServiceFaceRecord(BaseModel):
    """Face record used within services.
    
    This model represents face data for internal service operations.
    """
    face_id: str = Field(..., description="Unique identifier of the detected face")
    bounding_box: BoundingBox = Field(..., description="Face location in image")
    confidence: float = Field(..., description="Confidence score (0-100)")
    image_id: Optional[str] = Field(None, description="Source image identifier")
    
    @classmethod
    def from_face(cls, face: Face, face_id: str, image_id: Optional[str] = None) -> "ServiceFaceRecord":
        """Create a face record from a Face entity.
        
        Args:
            face: Face entity
            face_id: Unique identifier for the face
            image_id: Optional source image identifier
            
        Returns:
            ServiceFaceRecord: Face record
        """
        return cls(
            face_id=face_id,
            bounding_box=face.bounding_box,
            confidence=face.confidence,
            image_id=image_id
        )


class ServiceIndexFacesResponse(BaseModel):
    """Response model for face indexing service.
    
    This model represents the result of indexing faces within the service layer.
    """
    face_records: List[ServiceFaceRecord] = Field(..., description="List of indexed faces")
    detection_id: str = Field(..., description="Unique identifier for this detection operation")
    image_id: Optional[str] = Field(None, description="Source image identifier") 