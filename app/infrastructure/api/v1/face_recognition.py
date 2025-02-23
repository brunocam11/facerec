"""Face recognition API endpoints."""
from typing import List, Optional
import uuid
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
)
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from app.core.exceptions import (
    InvalidImageError,
    MultipleFacesError,
    NoFaceDetectedError,
    VectorStoreError,
)
from app.core.logging import get_logger
from app.domain.entities.face import BoundingBox, Face
from app.domain.value_objects.recognition import (
    DetectionResult,
    FaceMatch,
    SearchResult,
)
from app.infrastructure.storage.pinecone import PineconeVectorStore
from app.services import InsightFaceRecognitionService
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.infrastructure.dependencies import get_uow, get_indexing_service
from app.services.face_indexing import (
    FaceIndexingService,
    IndexingResult,
    FaceRecord
)

logger = get_logger(__name__)
router = APIRouter()


class FaceRecord(BaseModel):
    """Face record returned by face operations."""
    face_id: str = Field(...,
                        description="Unique identifier of the detected face")
    bounding_box: BoundingBox = Field(...,
                                     description="Face location in image")
    confidence: float = Field(..., description="Confidence score (0-100)")
    external_image_id: Optional[str] = Field(
        None, description="External image reference")


class DetectionResponse(BaseModel):
    """Response model for face detection endpoint."""
    face_records: List[FaceRecord] = Field(...,
                                          description="List of detected faces")


class IndexFacesResponse(IndexingResult):
    """Response model for face indexing endpoint."""
    pass


@router.post(
    "/faces/index",
    response_model=IndexFacesResponse,
    summary="Index faces from an image",
    description="Detects faces in an image and adds them to the specified collection for later search.",
    response_class=JSONResponse
)
async def index_faces(
    image: UploadFile = File(...),
    collection_id: str = Form(...),
    max_faces: int = Form(20),
    external_image_id: Optional[str] = Form(None),
    indexing_service: FaceIndexingService = Depends(get_indexing_service),
    uow: UnitOfWork = Depends(get_uow)
) -> IndexFacesResponse:
    """Index faces from an image for later search.
    
    Args:
        image: Image file containing faces to index
        collection_id: External system collection identifier
        max_faces: Maximum number of faces to index (default: 20)
        external_image_id: External image reference (optional)
        indexing_service: Face indexing service instance
        uow: Unit of work for database operations
        
    Returns:
        IndexFacesResponse containing the indexed face records
        
    Raises:
        HTTPException: If image processing or storage fails
    """
    try:
        # Read image bytes
        image_bytes = await image.read()
        
        # Delegate to service
        result = await indexing_service.index_faces(
            image_bytes=image_bytes,
            collection_id=collection_id,
            max_faces=max_faces,
            external_image_id=external_image_id,
            uow=uow
        )
        
        return IndexFacesResponse(**result.__dict__)
        
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


class SearchFacesResponse(BaseModel):
    """Response model for face search endpoint."""
    searched_face_id: str = Field(...,
                                 description="ID of the face used for search")
    face_matches: List[FaceMatch] = Field(...,
                                         description="Similar faces found")
