"""API specific face models."""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.entities.face import BoundingBox, Face
# Import the domain FaceMatch model (used implicitly in from_service_response)
from app.domain.value_objects.recognition import FaceMatch as DomainFaceMatch # Keep alias for clarity
from app.services.models import ServiceIndexFacesResponse, ServiceSearchResult
from app.core.config import settings # Import settings

# Constants for validation ranges used in API models
MIN_THRESHOLD = 0.0
MAX_THRESHOLD = 1.0


class FaceRecord(BaseModel):
    """API model for a single face record in responses."""
    face_id: str = Field(..., description="Unique identifier for the face")
    bounding_box: BoundingBox = Field(...,
                                      description="Face bounding box coordinates")
    confidence: float = Field(...,
                              description="Face detection confidence score",
                              ge=MIN_THRESHOLD, le=MAX_THRESHOLD)
    # S3 Key for the image associated with this face record
    image_key: Optional[str] = Field(None,
                                     description="S3 object key (path) of the source image")

    @classmethod
    def from_face(cls, face: Face, face_id: str, image_key: Optional[str] = None) -> "FaceRecord":
        """Create an API FaceRecord from a domain Face entity."""
        # Use provided image_key or try to get it from the Face object
        img_key = image_key or getattr(face, 'image_key', None)
        return cls(
            face_id=face_id,
            bounding_box=face.bounding_box,
            confidence=face.confidence,
            image_key=img_key
        )


class FaceIndexingRequest(BaseModel):
    """Request model for the /index endpoint."""
    bucket: str = Field(
        ...,
        description="S3 bucket containing the image",
        min_length=1, max_length=63, pattern="^[a-z0-9][a-z0-9.-]*[a-z0-9]$"
    )
    key: str = Field(
        ...,
        description="S3 object key (path) of the image",
        min_length=1, max_length=1024
    )
    collection_id: str = Field(
        ...,
        description="Collection where faces will be indexed",
        min_length=1, max_length=100, pattern="^[a-zA-Z0-9_-]+$"
    )
    max_faces: Optional[int] = Field(
        5,
        description="Maximum number of faces to index", ge=1, le=20
    )


class FaceIndexingResponse(BaseModel):
    """Response model for the /index endpoint."""
    face_records: List[FaceRecord] = Field(...,
                                           description="List of indexed face records")
    detection_id: str = Field(...,
                              description="Unique identifier for the detection operation")
    image_key: str = Field(...,
                           description="S3 object key (path) of the source image")

    @classmethod
    def from_service_response(cls, service_response: ServiceIndexFacesResponse) -> "FaceIndexingResponse":
        """Convert the service layer response (ServiceIndexFacesResponse) to the API response model."""
        api_face_records = [
            FaceRecord(
                face_id=record.face_id,
                bounding_box=record.bounding_box,
                confidence=record.confidence,
                image_key=record.image_key
            )
            for record in service_response.face_records
        ]
        return cls(
            face_records=api_face_records,
            detection_id=service_response.detection_id,
            image_key=service_response.image_key
        )


class FaceMatchingRequest(BaseModel):
    """Request model for the /match endpoint."""
    bucket: str = Field(
        ...,
        description="S3 bucket containing the query image",
        min_length=1, max_length=63, pattern="^[a-z0-9][a-z0-9.-]*[a-z0-9]$"
    )
    key: str = Field(
        ...,
        description="S3 object key (path) of the query image",
        min_length=1, max_length=1024
    )
    collection_id: str = Field(
        ...,
        description="Collection to search in",
        min_length=1, max_length=100, pattern="^[a-zA-Z0-9_-]+$"
    )
    threshold: float = Field(
        0.8,
        description="Minimum similarity score for matches (0.0 to 1.0)",
        ge=MIN_THRESHOLD, le=MAX_THRESHOLD
    )
    max_matches: Optional[int] = Field(
        default=10,
        ge=1,
        le=settings.MAX_MATCHES,
        description=f"Maximum number of matches to return (1-{settings.MAX_MATCHES})"
    )


# Define the FaceMatch model specifically for the API response
class FaceMatch(BaseModel):
    """API model representing a single face match in the response."""
    face_id: str = Field(...,
                         description="Unique identifier for the matched face")
    similarity: float = Field(...,
                              description="Similarity score (0.0 to 1.0)",
                              ge=MIN_THRESHOLD, le=MAX_THRESHOLD)
    image_key: str = Field(...,
                         description="S3 object key (path) of the source image")


class FaceMatchingResponse(BaseModel):
    """Response model for the /match endpoint."""
    searched_face_id: str = Field(...,
                                  description="Unique identifier for the face used in the search")
    face_matches: List[FaceMatch] = Field(...,
                                          description="List of matching faces found")

    @classmethod
    def from_service_response(cls, service_response: ServiceSearchResult) -> "FaceMatchingResponse":
        """Convert the service layer response (ServiceSearchResult) to the API response model."""
        api_face_matches = []
        # Loop through domain objects and convert to API objects.
        for domain_match in service_response.face_matches:
            api_match = FaceMatch(
                face_id=domain_match.face_id,
                similarity=domain_match.similarity,
                image_key=domain_match.image_key
            )
            api_face_matches.append(api_match)

        return cls(
            searched_face_id=service_response.searched_face_id,
            face_matches=api_face_matches
        )
