"""Face recognition API endpoints."""
from fastapi import APIRouter, HTTPException

from app.api.models.face import (
    FaceIndexingRequest,
    FaceIndexingResponse,
    FaceMatchingRequest,
    FaceMatchingResponse,
)
from app.core.container import container
from app.core.exceptions import (
    InvalidImageError,
    NoFaceDetectedError,
    StorageError,
    VectorStoreError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(
    tags=["face-recognition"],
    responses={
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"}
    }
)

# Constants for validation
MIN_THRESHOLD = 0.0
MAX_THRESHOLD = 1.0


@router.post(
    "/index",
    response_model=FaceIndexingResponse,
    summary="Index faces in an image",
    description="Detects faces in an image and stores their embeddings in a collection.",
    responses={
        200: {
            "description": "Faces successfully indexed",
            "content": {
                "application/json": {
                    "example": {
                        "face_records": [
                            {
                                "face_id": "550e8400-e29b-41d4-a716-446655440000",
                                "bounding_box": {
                                    "left": 100,
                                    "top": 200,
                                    "width": 150,
                                    "height": 150,
                                },
                                "confidence": 0.99,
                                "image_key": "photos/user123/image.jpg",
                            }
                        ],
                        "detection_id": "123e4567-e89b-12d3-a456-426614174000",
                        "image_key": "photos/user123/image.jpg",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid image format. Only JPEG and PNG are supported."
                    }
                }
            },
        },
        404: {
            "description": "Image not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Image not found in S3 bucket"}
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to process image"}
                }
            },
        },
    },
)
async def index_faces(request: FaceIndexingRequest) -> FaceIndexingResponse:
    """Index faces in an image stored in S3.

    Args:
        request: Face indexing request containing image location and parameters

    Returns:
        FaceIndexingResponse containing indexed face records

    Raises:
        HTTPException: If the request is invalid or processing fails
    """
    try:
        result = await container.face_indexing_service.index_faces(
            bucket=request.bucket,
            key=request.key,
            collection_id=request.collection_id,
            max_faces=request.max_faces,
        )
        return FaceIndexingResponse.from_service_response(result)

    except InvalidImageError as e:
        logger.error("Invalid image format", error=str(e))
        raise HTTPException(
            status_code=400,
            detail="Invalid image format. Only JPEG and PNG are supported."
        )
    except NoFaceDetectedError as e:
        logger.warning("No faces detected in image", error=str(e))
        return FaceIndexingResponse(face_records=[], detection_id="", image_key=request.key)
    except StorageError as e:
        logger.error("Failed to retrieve image from S3", error=str(e))
        raise HTTPException(
            status_code=404,
            detail="Image not found or inaccessible"
        )
    except VectorStoreError as e:
        logger.error("Failed to store face embeddings", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to store face data"
        )
    except Exception as e:
        logger.error("Unexpected error during face indexing",
                     error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the request"
        )


@router.post(
    "/match",
    response_model=FaceMatchingResponse,
    summary="Match faces in a collection",
    description="Finds similar faces in a collection based on a query image.",
    responses={
        200: {
            "description": "Faces successfully matched",
            "content": {
                "application/json": {
                    "example": {
                        "searched_face_id": "550e8400-e29b-41d4-a716-446655440000",
                        "face_matches": [
                            {
                                "face_id": "550e8400-e29b-41d4-a716-446655440001",
                                "similarity": 0.95,
                                "image_id": "image123",
                            }
                        ],
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid image format. Only JPEG and PNG are supported."
                    }
                }
            },
        },
        404: {
            "description": "Image not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Image not found in S3 bucket"}
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to process image"}
                }
            },
        },
    },
)
async def match_faces(request: FaceMatchingRequest) -> FaceMatchingResponse:
    """Match faces in a collection based on a query image in S3.

    Args:
        request: Face matching request containing query image location and parameters

    Returns:
        FaceMatchingResponse containing matching face records

    Raises:
        HTTPException: If the request is invalid or processing fails
    """
    try:
        result = await container.face_matching_service.match_faces_in_a_collection(
            bucket=request.bucket,
            key=request.key,
            collection_id=request.collection_id,
            threshold=request.threshold,
        )
        return FaceMatchingResponse.from_service_response(result)

    except InvalidImageError as e:
        logger.error("Invalid image format", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except NoFaceDetectedError as e:
        logger.warning("No faces detected in query image", error=str(e))
        return FaceMatchingResponse(searched_face_id="", face_matches=[])
    except StorageError as e:
        logger.error("Failed to retrieve image from S3", error=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except VectorStoreError as e:
        logger.error("Failed to search face embeddings", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error during face matching",
                     error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process image")
