"""Face recognition API endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from app.api.models.face import IndexFacesResponse
from app.core.exceptions import InvalidImageError, NoFaceDetectedError, VectorStoreError
from app.core.logging import get_logger
from app.infrastructure.dependencies import get_indexing_service
from app.services.face_indexing import FaceIndexingService

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
