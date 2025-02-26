"""Face recognition value objects."""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.entities.face import Face


class DetectionResult(BaseModel):
    """Result of face detection operation."""
    faces: List[Face] = Field(..., description="List of detected faces")


class FaceMatch(BaseModel):
    """Face match result from search operation."""
    face_id: str = Field(..., description="External system face identifier")
    similarity: float = Field(..., description="Similarity score with searched face")
    external_image_id: Optional[str] = Field(None, description="External system image identifier")


class SearchResult(BaseModel):
    """Result of face search operation."""
    searched_face_id: str = Field(..., description="External system face identifier")
    face_matches: List[FaceMatch] = Field(..., description="List of matching faces")


class ComparisonResult(BaseModel):
    """Result of face comparison operation."""
    source_face: Face = Field(..., description="Source face for comparison")
    target_face: Face = Field(..., description="Target face being compared")
    similarity: float = Field(..., description="Similarity score between faces")
    matches: bool = Field(..., description="Whether the faces match based on threshold") 