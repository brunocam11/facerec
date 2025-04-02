"""API specific face models."""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.entities.face import BoundingBox, Face
from app.domain.value_objects.recognition import FaceMatch


class FaceRecord(BaseModel):
    """Face record returned by API operations.
    
    This model represents the public API contract for face data.
    It excludes sensitive information like embeddings.
    """
    face_id: str = Field(..., description="Unique identifier of the detected face")
    bounding_box: BoundingBox = Field(..., description="Face location in image")
    confidence: float = Field(..., description="Confidence score (0-100)")
    image_id: Optional[str] = Field(None, description="Source image identifier")

    @classmethod
    def from_face(cls, face: Face, face_id: str, image_id: Optional[str] = None) -> "FaceRecord":
        """Create an API record from a face entity.
        
        Args:
            face: Face entity
            face_id: Unique identifier for the face
            image_id: Optional source image identifier
            
        Returns:
            FaceRecord instance for API response
        """
        return cls(
            face_id=face_id,
            bounding_box=face.bounding_box,
            confidence=face.confidence,
            image_id=image_id
        )


class DetectionResponse(BaseModel):
    """Response model for face detection endpoint."""
    face_records: List[FaceRecord] = Field(..., description="List of detected faces")


class IndexFacesResponse(BaseModel):
    """Response model for face indexing endpoint."""
    face_records: List[FaceRecord] = Field(..., description="List of indexed faces")
    detection_id: str = Field(..., description="Unique identifier for this detection operation")
    image_id: Optional[str] = Field(None, description="Source image identifier")


class MatchFacesResponse(BaseModel):
    """Response model for face matching endpoint."""
    face_matches: List[FaceMatch] = Field(..., description="Similar faces found")


class IndexFacesRequest(BaseModel):
    """Request for face indexing operation."""
    bucket: str = Field(..., description="S3 bucket containing the image")
    object_key: str = Field(..., description="S3 object key for the image")
    collection_id: str = Field(..., description="Collection where faces will be indexed")
    image_id: str = Field(..., description="Source image identifier")
    max_faces: Optional[int] = Field(5, description="Maximum number of faces to index")


class MatchFacesRequest(BaseModel):
    """Request for face matching operation."""
    bucket: str = Field(..., description="S3 bucket containing the query image")
    object_key: str = Field(..., description="S3 object key for the query image")
    collection_id: str = Field(..., description="Collection to search in")
    threshold: float = Field(0.5, description="Similarity threshold") 