"""Face indexing service for detecting and storing face embeddings."""
import uuid
from typing import List, Optional

from app.core.exceptions import InvalidImageError, NoFaceDetectedError, VectorStoreError
from app.core.logging import get_logger
from app.domain.entities import BoundingBox
from app.domain.entities.face import Face
from app.infrastructure.vectordb import PineconeVectorStore
from app.infrastructure.vectordb.models import VectorFaceRecord
from app.services import InsightFaceRecognitionService
from app.services.models import ServiceFaceRecord, ServiceIndexFacesResponse

logger = get_logger(__name__)


class FaceIndexingService:
    """Service for detecting and indexing faces in images.

    This service:
    1. Detects faces in images using InsightFace
    2. Extracts face embeddings
    3. Stores embeddings in a vector database (Pinecone)
    4. Maintains idempotency by checking for existing faces

    Example:
        ```python
        face_service = InsightFaceRecognitionService()
        vector_store = PineconeVectorStore()
        indexer = FaceIndexingService(face_service, vector_store)

        with open("image.jpg", "rb") as f:
            image_bytes = f.read()

        result = await indexer.index_faces(
            image_id="unique_image_id",
            image_bytes=image_bytes,
            collection_id="my_collection",
            max_faces=5
        )
        ```
    """

    def __init__(
        self,
        face_service: InsightFaceRecognitionService,
        vector_store: PineconeVectorStore,
    ) -> None:
        """Initialize face indexing service.

        Args:
            face_service: Service for face detection and embedding extraction
            vector_store: Vector database for storing face embeddings
        """
        self._face_service = face_service
        self._vector_store = vector_store

    async def index_faces(
        self,
        image_id: str,
        image_bytes: bytes,
        collection_id: str,
        max_faces: Optional[int] = 5,
    ) -> ServiceIndexFacesResponse:
        """Index faces from image bytes.

        If the image_id already exists in the collection, returns the existing face records
        without reprocessing the image. This ensures idempotency and prevents duplicate
        processing of the same image.

        Args:
            image_id: Source image identifier
            image_bytes: Raw image bytes
            collection_id: Collection where faces will be stored
            max_faces: Optional maximum number of faces to index

        Returns:
            ServiceIndexFacesResponse containing the indexed face records

        Raises:
            InvalidImageError: If the image format is invalid or corrupted
            NoFaceDetectedError: If no faces are detected in the image
            VectorStoreError: If storing faces in the vector database fails
        """
        try:
            # Check if image was already processed
            existing_faces, detection_id = await self._vector_store.get_faces_by_image_id(
                image_id=image_id,
                collection_id=collection_id
            )

            if existing_faces:
                logger.info(
                    "Image already indexed, returning existing records",
                    image_id=image_id,
                    collection_id=collection_id,
                    faces_count=len(existing_faces),
                    detection_id=detection_id
                )
                return self._convert_existing_faces_to_response(
                    existing_faces, image_id, detection_id
                )

            # Generate new detection_id for new processing
            detection_id = str(uuid.uuid4())
            logger.info(
                "Processing new image",
                image_id=image_id,
                collection_id=collection_id,
                detection_id=detection_id
            )

            # Detect and extract embeddings for new image
            faces = await self._face_service.get_faces_with_embeddings(
                image_bytes,
                max_faces=max_faces
            )

            if not faces:
                logger.warning(
                    "No faces detected in image",
                    image_id=image_id,
                    collection_id=collection_id
                )
                return ServiceIndexFacesResponse(
                    face_records=[],
                    detection_id=detection_id,
                    image_id=image_id
                )

            face_records = []
            for face in faces:
                face_record = await self._store_face(
                    face=face,
                    collection_id=collection_id,
                    image_id=image_id,
                    detection_id=detection_id
                )
                face_records.append(face_record)

            logger.info(
                "Successfully indexed faces",
                collection_id=collection_id,
                faces_count=len(face_records),
                image_id=image_id,
                detection_id=detection_id
            )

            return ServiceIndexFacesResponse(
                face_records=face_records,
                detection_id=detection_id,
                image_id=image_id
            )

        except InvalidImageError as e:
            logger.error(
                "Invalid image format",
                error=str(e),
                image_id=image_id
            )
            raise
        except NoFaceDetectedError as e:
            logger.warning(
                "No faces detected in image",
                error=str(e),
                image_id=image_id
            )
            raise
        except VectorStoreError as e:
            logger.error(
                "Failed to store faces in vector database",
                error=str(e),
                image_id=image_id,
                collection_id=collection_id
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during face indexing",
                error=str(e),
                image_id=image_id,
                collection_id=collection_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to index faces: {str(e)}")

    def _convert_existing_faces_to_response(
        self,
        existing_faces: List[VectorFaceRecord],
        image_id: str,
        detection_id: str
    ) -> ServiceIndexFacesResponse:
        """Convert existing vector records to API response format.

        Args:
            existing_faces: List of existing face records from vector store
            image_id: Source image identifier
            detection_id: Original detection operation ID

        Returns:
            ServiceIndexFacesResponse with converted face records
        """
        face_records = []
        for face in existing_faces:
            bounding_box = BoundingBox(
                left=face.bbox_left,
                top=face.bbox_top,
                width=face.bbox_width,
                height=face.bbox_height
            )
            face_records.append(ServiceFaceRecord(
                face_id=face.face_id,
                bounding_box=bounding_box,
                confidence=face.confidence,
                image_id=image_id
            ))

        return ServiceIndexFacesResponse(
            face_records=face_records,
            detection_id=detection_id,
            image_id=image_id
        )

    async def _store_face(
        self,
        face: Face,
        collection_id: str,
        image_id: Optional[str],
        detection_id: str
    ) -> ServiceFaceRecord:
        """Store face in vector database and return API response record.

        Args:
            face: Face entity with embedding
            collection_id: Collection where face will be stored
            image_id: Source image identifier
            detection_id: ID grouping faces from same detection operation

        Returns:
            ServiceFaceRecord formatted for API response

        Raises:
            ValueError: If face has no embedding vector
            VectorStoreError: If storing face in vector database fails
        """
        try:
            face_id = str(uuid.uuid4())

            # Create vector database record
            vector_record = VectorFaceRecord.from_face(
                face=face,
                face_id=face_id,
                collection_id=collection_id,
                detection_id=detection_id,
                image_id=image_id
            )

            # Store in vector database
            await self._vector_store.store_face(
                face=face,
                collection_id=collection_id,
                image_id=image_id,
                face_id=face_id,
                detection_id=detection_id
            )

            logger.debug(
                "Stored face in vector database",
                face_id=face_id,
                collection_id=collection_id,
                image_id=image_id
            )

            # Create API response record
            return ServiceFaceRecord.from_face(
                face=face,
                face_id=face_id,
                image_id=image_id
            )

        except ValueError as e:
            logger.error(
                "Face missing required data",
                error=str(e),
                face_id=face_id,
                collection_id=collection_id
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to store face in vector database",
                error=str(e),
                face_id=face_id,
                collection_id=collection_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to store face: {str(e)}")
