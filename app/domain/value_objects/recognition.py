"""Face recognition value objects."""
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from app.domain.entities.face import Face


@dataclass
class DetectionResult:
    """Result of face detection operation."""
    faces: List[Face]


@dataclass
class FaceMatch:
    """Face match result from search operation."""
    face_id: UUID
    similarity: float
    external_image_id: Optional[str] = None


@dataclass
class SearchResult:
    """Result of face search operation."""
    searched_face_id: UUID
    face_matches: List[FaceMatch]


@dataclass 
class ComparisonResult:
    """Result of face comparison operation."""
    source_face: Face
    target_face: Face
    similarity: float
    matches: bool 