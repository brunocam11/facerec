"""API specific face models."""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.entities.face import BoundingBox, Face
from app.domain.value_objects.recognition import FaceMatch
from app.services.models import ServiceIndexFacesResponse, ServiceSearchResult


class FaceRecord(BaseModel):
    """Face record returned by API operations.

    This model represents the public API contract for face data.
    It excludes sensitive information like embeddings.
    """
    face_id: str = Field(..., description="Unique identifier for the face")
    bounding_box: BoundingBox = Field(...,
                                      description="Face bounding box coordinates")
    confidence: float = Field(...,
                              description="Face detection confidence score", ge=0.0, le=1.0)
    image_key: str = Field(...,
                           description="S3 object key (path) of the source image")

    @classmethod
    def from_face(cls, face: Face, face_id: str, image_key: Optional[str] = None) -> "FaceRecord":
        """Create an API record from a face entity.

        Args:
            face: Face entity
            face_id: Unique identifier for the face
            image_key: S3 object key (path) of the source image

        Returns:
            FaceRecord instance for API response
        """
        return cls(
            face_id=face_id,
            bounding_box=face.bounding_box,
            confidence=face.confidence,
            image_key=image_key
        )

class FaceIndexingRequest(BaseModel):
    """Request model for indexing faces."""
    bucket: str = Field(
        ...,
        description="S3 bucket containing the image",
        min_length=1,
        max_length=63,
        pattern="^[a-z0-9][a-z0-9.-]*[a-z0-9]$"
    )
    key: str = Field(
        ...,
        description="S3 object key (path) of the image",
        min_length=1,
        max_length=1024
    )
    collection_id: str = Field(
        ...,
        description="Collection where faces will be indexed",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_-]+$"
    )
    max_faces: Optional[int] = Field(
        5,
        description="Maximum number of faces to index",
        ge=1,
        le=20
    )


class FaceIndexingResponse(BaseModel):
    """Response model for indexed faces."""
    face_records: List[FaceRecord] = Field(...,
                                           description="List of indexed face records")
    detection_id: str = Field(...,
                              description="Unique identifier for the detection operation")
    image_key: str = Field(...,
                           description="S3 object key (path) of the source image")

    @classmethod
    def from_service_response(cls, service_response: ServiceIndexFacesResponse) -> "FaceIndexingResponse":
        """Convert service response to API response.

        Args:
            service_response: Service layer response

        Returns:
            API layer response
        """
        face_records = [
            FaceRecord(
                face_id=record.face_id,
                bounding_box=record.bounding_box,
                confidence=record.confidence,
                image_key=record.image_key
            )
            for record in service_response.face_records
        ]

        return cls(
            face_records=face_records,
            detection_id=service_response.detection_id,
            image_key=service_response.image_key
        )


class FaceMatchingRequest(BaseModel):
    """Request model for matching faces."""
    bucket: str = Field(
        ...,
        description="S3 bucket containing the query image",
        min_length=1,
        max_length=63,
        pattern="^[a-z0-9][a-z0-9.-]*[a-z0-9]$"
    )
    key: str = Field(
        ...,
        description="S3 object key (path) of the query image",
        min_length=1,
        max_length=1024
    )
    collection_id: str = Field(
        ...,
        description="Collection to search in",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_-]+$"
    )
    threshold: float = Field(
        0.5,
        description="Minimum similarity score for matches (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )


class FaceMatch(BaseModel):
    """API model for a face match."""
    face_id: str = Field(...,
                         description="Unique identifier for the matched face")
    similarity: float = Field(...,
                              description="Similarity score (0.0 to 1.0)", ge=0.0, le=1.0)
    key: str = Field(...,
                     description="S3 object key (path) of the source image")


class FaceMatchingResponse(BaseModel):
    """Response model for face matches."""
    searched_face_id: str = Field(...,
                                  description="Unique identifier for the searched face")
    face_matches: List[FaceMatch] = Field(...,
                                          description="List of matching faces")

    @classmethod
    def from_service_response(cls, service_response: ServiceSearchResult) -> "FaceMatchingResponse":
        """Convert service response to API response.

        Args:
            service_response: Service layer response

        Returns:
            API layer response
        """
        face_matches = [
            FaceMatch(
                face_id=match.face_id,
                similarity=match.similarity,
                key=match.key
            )
            for match in service_response.face_matches
        ]

        return cls(
            searched_face_id=service_response.searched_face_id,
            face_matches=face_matches
        )
