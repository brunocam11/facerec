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


class IndexFacesResponse(BaseModel):
    """Response model for face indexing endpoint."""
    face_records: List[FaceRecord] = Field(...,
                                          description="List of indexed faces")
    image_id: str = Field(..., description="ID of the processed image")
    external_image_id: Optional[str] = Field(
        None, description="External image reference")


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
    face_service: InsightFaceRecognitionService = Depends(),
    vector_store: PineconeVectorStore = Depends()
) -> IndexFacesResponse:
    """Index faces from an image for later search.

    This endpoint:
    1. Detects faces in the uploaded image
    2. Extracts face embeddings
    3. Stores the embeddings in the vector database
    4. Returns metadata about the indexed faces

    Args:
        image: Image file containing faces to index
        collection_id: External system collection identifier
        max_faces: Maximum number of faces to index (default: 20)
        external_image_id: External image reference (optional)
        face_service: Face recognition service instance
        vector_store: Vector storage service instance

    Returns:
        IndexFacesResponse containing the indexed face records

    Raises:
        HTTPException: If image processing or storage fails
    """
    try:
        # Read image bytes
        image_bytes = await image.read()

        # Generate internal UUIDs
        internal_image_id = uuid.uuid4()

        # Detect and extract embeddings for faces
        faces = await face_service.get_faces_with_embeddings(
            image_bytes,
            max_faces=max_faces
        )

        face_records = []
        # Store each face in the vector database
        for face in faces:
            # Generate internal UUID for face
            internal_face_id = uuid.uuid4()

            # Store in vector database using string representations
            await vector_store.store_face(
                face=face,
                collection_id=collection_id,  # External ID stays as string
                image_id=str(internal_image_id),
                face_detection_id=str(internal_face_id)
            )

            # Create face record for response
            face_records.append(FaceRecord(
                face_id=str(internal_face_id),  # Convert UUID to string for external systems
                bounding_box=face.bounding_box,
                confidence=face.confidence,
                external_image_id=external_image_id
            ))

        logger.info(
            "Successfully indexed faces",
            internal_image_id=internal_image_id,
            collection_id=collection_id,
            faces_count=len(face_records)
        )

        return IndexFacesResponse(
            face_records=face_records,
            image_id=str(internal_image_id),  # Convert UUID to string for external systems
            external_image_id=external_image_id
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
            "Unexpected error during face indexing",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the request"
        )


class SearchFacesResponse(BaseModel):
    """Response model for face search endpoint."""
    searched_face_id: str = Field(...,
                                 description="ID of the face used for search")
    face_matches: List[FaceMatch] = Field(...,
                                         description="Similar faces found")
