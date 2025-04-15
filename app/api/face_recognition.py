"""Face recognition API endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import Field

from app.api.models.face import IndexFacesResponse, FaceRecord
from app.core.exceptions import InvalidImageError, NoFaceDetectedError, VectorStoreError
from app.core.logging import get_logger
from app.domain.value_objects.recognition import SearchResult
from app.infrastructure.dependencies import (
    get_face_matching_service,
    get_indexing_service,
)
from app.services.face_indexing import FaceIndexingService
from app.services.face_matching import FaceMatchingService
from app.services.models import ServiceFaceRecord, ServiceIndexFacesResponse

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/v1",
    tags=["face-recognition"],
    responses={
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"}
    }
)

# Constants for validation
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
MIN_THRESHOLD = 0.0
MAX_THRESHOLD = 1.0

# Helper function to convert service models to API models
def _convert_service_response_to_api_response(
    service_response: ServiceIndexFacesResponse
) -> IndexFacesResponse:
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
            image_id=record.image_id
        )
        for record in service_response.face_records
    ]
    
    return IndexFacesResponse(
        face_records=face_records,
        detection_id=service_response.detection_id,
        image_id=service_response.image_id
    )


@router.post(
    "/faces/index",
    response_model=IndexFacesResponse,
    summary="Index faces from an image",
    description="""
    Detects faces in an image and adds them to the specified collection for later search.
    
    The image must be in JPEG or PNG format and not exceed 10MB in size.
    Each face detected will be assigned a unique ID and stored in the vector database.
    """,
    response_class=JSONResponse,
    responses={
        200: {
            "description": "Faces successfully indexed",
            "content": {
                "application/json": {
                    "example": {
                        "face_records": [
                            {
                                "face_id": "face-123",
                                "bounding_box": {"left": 100, "top": 200, "width": 150, "height": 150},
                                "confidence": 0.95,
                                "image_id": "img-456"
                            }
                        ],
                        "detection_id": "det-789",
                        "image_id": "img-456"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No faces were detected in the image"
                    }
                }
            }
        }
    }
)
async def index_faces(
    image: UploadFile = File(
        ...,
        description="Image file containing faces to index (JPEG or PNG, max 10MB)",
        max_length=MAX_FILE_SIZE
    ),
    collection_id: str = Form(
        ...,
        description="Collection where faces will be indexed",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_-]+$"
    ),
    image_id: str = Form(
        ...,
        description="Source image identifier",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_-]+$"
    ),
    max_faces: Optional[int] = Form(
        5,
        description="Maximum number of faces to index",
        ge=1,
        le=20
    ),
    indexing_service: FaceIndexingService = Depends(get_indexing_service),
) -> IndexFacesResponse:
    """Index faces from an image for later search.

    Args:
        image: Image file containing faces to index (JPEG or PNG, max 10MB)
        collection_id: Collection where faces will be stored (alphanumeric with underscores and hyphens)
        image_id: Source image identifier (alphanumeric with underscores and hyphens)
        max_faces: Maximum number of faces to index (1-20, default: 5)
        indexing_service: Face indexing service instance

    Returns:
        IndexFacesResponse containing the indexed face records

    Raises:
        HTTPException: If image processing or storage fails
    """
    try:
        # Validate file type
        if image.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}"
            )

        # Read image bytes
        image_bytes = await image.read()

        # Delegate to service
        service_response = await indexing_service.index_faces(
            image_id=image_id,
            image_bytes=image_bytes,
            collection_id=collection_id,
            max_faces=max_faces,
        )

        return _convert_service_response_to_api_response(service_response)

    except NoFaceDetectedError:
        raise HTTPException(
            status_code=400,
            detail="No faces were detected in the image"
        )
    except InvalidImageError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image format: {str(e)}"
        )
    except VectorStoreError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store face embeddings: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Face indexing failed",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred"
        )


@router.post(
    "/faces/match",
    response_model=SearchResult,
    summary="Match faces in a collection",
    description="""
    Find similar faces in a specific collection based on a query image.
    
    The image must be in JPEG or PNG format and not exceed 10MB in size.
    The threshold parameter controls how similar faces must be to be considered a match.
    """,
    response_class=JSONResponse,
    responses={
        200: {
            "description": "Faces successfully matched",
            "content": {
                "application/json": {
                    "example": {
                        "searched_face_id": "face-123",
                        "face_matches": [
                            {
                                "face_id": "face-456",
                                "similarity": 0.95,
                                "bounding_box": {"left": 100, "top": 200, "width": 150, "height": 150}
                            }
                        ]
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No face detected in the query image"
                    }
                }
            }
        }
    }
)
async def match_faces(
    image: UploadFile = File(
        ...,
        description="Image file containing faces to match (JPEG or PNG, max 10MB)",
        max_length=MAX_FILE_SIZE
    ),
    collection_id: str = Form(
        ...,
        description="Collection to search in",
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_-]+$"
    ),
    threshold: float = Form(
        0.5,
        description="Similarity threshold (0.0 to 1.0)",
        ge=MIN_THRESHOLD,
        le=MAX_THRESHOLD
    ),
    face_matching_service: FaceMatchingService = Depends(get_face_matching_service),
) -> SearchResult:
    """Match faces in a collection.

    Args:
        image: Image file containing faces to match (JPEG or PNG, max 10MB)
        collection_id: Collection to search in (alphanumeric with underscores and hyphens)
        threshold: Similarity threshold (0.0 to 1.0)
        face_matching_service: Face matching service instance

    Returns:
        SearchResult containing the query face and the similar faces

    Raises:
        HTTPException: If image processing or storage fails
    """
    try:
        # Validate file type
        if image.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}"
            )

        # Read image bytes
        image_bytes = await image.read()

        return await face_matching_service.match_faces_in_a_collection(
            image_bytes=image_bytes,
            collection_id=collection_id,
            threshold=threshold,
        )

    except Exception as e:
        logger.error(
            "Face matching failed",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred"
        )
