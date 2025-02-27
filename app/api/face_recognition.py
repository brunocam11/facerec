"""Face recognition API endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.responses import JSONResponse

from app.api.models.face import IndexFacesResponse
from app.core.exceptions import InvalidImageError, NoFaceDetectedError, VectorStoreError
from app.core.logging import get_logger
from app.domain.value_objects.recognition import SearchResult
from app.infrastructure.dependencies import (
    get_face_matching_service,
    get_indexing_service,
)
from app.services.face_indexing import FaceIndexingService
from app.services.face_matching import FaceMatchingService

logger = get_logger(__name__)
router = APIRouter()


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
        return await indexing_service.index_faces(
            image_id=image_id,
            image_bytes=image_bytes,
            collection_id=collection_id,
            max_faces=max_faces,
        )

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
    image: UploadFile = File(...),
    collection_id: str = Form(..., description="Collection to search in"),
    threshold: float = Form(0.5, description="Similarity threshold"),
    face_matching_service: FaceMatchingService = Depends(
        get_face_matching_service),
) -> SearchResult:
    """Match faces in a collection.

    Args:
        image: Image file containing faces to match
        collection_id: Collection to search in
        threshold: Similarity threshold
        face_matching_service: Face matching service instance

    Returns:
        SearchResult containing the query face and the similar faces

    Raises:
        HTTPException: If image processing or storage fails
    """
    try:
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
