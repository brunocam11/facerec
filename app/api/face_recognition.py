"""Face recognition API endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, File, UploadFile
from starlette.responses import JSONResponse

from app.api.models.face import (
    IndexFacesResponse,
    MatchFacesRequest,
    FaceRecord,
)
from app.core.exceptions import FileServiceError, InvalidImageError, NoFaceDetectedError, VectorStoreError
from app.core.logging import get_logger
from app.domain.value_objects.recognition import SearchResult
from app.infrastructure.dependencies import (
    get_face_matching_service,
    get_indexing_service,
    get_s3_service,
)
from app.services.face_indexing import FaceIndexingService
from app.services.face_matching import FaceMatchingService
from app.services.models import ServiceFaceRecord, ServiceIndexFacesResponse
from app.services.aws.s3 import S3Service

logger = get_logger(__name__)
router = APIRouter()

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
    description="Detects faces in an image and adds them to the specified collection for later search.",
    response_class=JSONResponse
)
async def index_faces(
    image: UploadFile = File(...),
    collection_id: str = Form(...,
                              description="Collection where faces will be indexed"),
    image_id: str = Form(..., description="Source image identifier"),
    max_faces: Optional[int] = Form(5),
    indexing_service: FaceIndexingService = Depends(get_indexing_service),
) -> IndexFacesResponse:
    """Index faces from an image for later search.

    Args:
        image: Image file containing faces to index
        collection_id: Collection where faces will be stored
        image_id: Source image identifier
        max_faces: Maximum number of faces to index (default: 5)
        indexing_service: Face indexing service instance

    Returns:
        IndexFacesResponse containing the indexed face records

    Raises:
        HTTPException: If image processing or storage fails
    """
    try:
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
    description="Find similar faces in a specific collection based on a query image.",
    response_class=JSONResponse
)
async def match_faces(
    request: MatchFacesRequest,
    face_matching_service: FaceMatchingService = Depends(
        get_face_matching_service),
    s3_service: S3Service = Depends(get_s3_service),
) -> SearchResult:
    """Match faces in a collection.

    Args:
        request: Match faces request containing S3 and collection details
        face_matching_service: Face matching service instance
        s3_service: S3 service instance

    Returns:
        SearchResult containing the query face and the similar faces

    Raises:
        HTTPException: If image processing or storage fails
    """
    try:
        # Get image from S3 using s3 service
        image_bytes = await s3_service.get_file_bytes(request.bucket, request.object_key)

        return await face_matching_service.match_faces_in_a_collection(
            image_bytes=image_bytes,
            collection_id=request.collection_id,
            threshold=request.threshold,
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
