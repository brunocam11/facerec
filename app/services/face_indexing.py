"""Face indexing service for detecting and storing face embeddings."""
import uuid
from typing import List, Optional

from app.core.exceptions import (
    InvalidImageError,
    NoFaceDetectedError,
    StorageError,
    VectorStoreError,
)
from app.core.logging import get_logger
from app.domain.entities.face import Face
from app.domain.interfaces.storage.vector_store import VectorStore
from app.services import InsightFaceRecognitionService
from app.services.aws.s3 import S3Service
from app.services.models import ServiceFaceRecord, ServiceIndexFacesResponse

logger = get_logger(__name__)


class FaceIndexingService:
    """Service for indexing faces in images.

    This service handles the process of detecting faces in images, extracting their embeddings,
    and storing them in a vector database for later retrieval.

    Example:
        ```python
        s3_service = S3Service()
        vector_store = PineconeVectorStore()
        recognition_service = InsightFaceRecognitionService()
        service = FaceIndexingService(s3_service, vector_store, recognition_service)

        result = await service.index_faces(
            bucket="my-bucket",
            key="photos/user123/image.jpg",
            collection_id="my-collection",
            max_faces=5
        )
        ```
    """

    def __init__(
        self,
        s3_service: S3Service,
        vector_store: VectorStore,
        recognition_service: InsightFaceRecognitionService,
    ) -> None:
        """Initialize the face indexing service.

        Args:
            s3_service: Service for S3 operations
            vector_store: Vector database for storing face embeddings
            recognition_service: Service for face detection and recognition
        """
        self._s3_service = s3_service
        self._vector_store = vector_store
        self._recognition_service = recognition_service

    async def index_faces(
        self,
        bucket: str,
        key: str,
        collection_id: str,
        max_faces: Optional[int] = 5,
    ) -> ServiceIndexFacesResponse:
        """Index faces from an image in S3.

        If the key already exists in the collection, returns the existing face records
        without reprocessing the image. This ensures idempotency and prevents duplicate
        processing of the same image.

        Args:
            bucket: S3 bucket containing the image
            key: S3 object key (path) of the image
            collection_id: Collection where faces will be stored
            max_faces: Optional maximum number of faces to index

        Returns:
            ServiceIndexFacesResponse containing the indexed face records

        Raises:
            InvalidImageError: If the image format is invalid or corrupted
            NoFaceDetectedError: If no faces are detected in the image
            VectorStoreError: If storing faces in the vector database fails
            StorageError: If the image cannot be retrieved from S3
        """
        try:
            # Use the updated interface method name
            existing_faces, detection_id = await self._vector_store.get_faces_by_image_key(
                image_key=key,
                collection_id=collection_id
            )

            # existing_faces is now List[Face]
            if existing_faces:
                logger.info(
                    "Image already indexed, returning existing records",
                    key=key,
                    collection_id=collection_id,
                    faces_count=len(existing_faces),
                    detection_id=detection_id
                )
                # Pass List[Face] to the updated helper
                return self._convert_existing_faces_to_response(
                    existing_faces, key, detection_id
                )

            # Generate new detection_id for new processing
            detection_id = str(uuid.uuid4())
            logger.info(
                "Processing new image",
                key=key,
                collection_id=collection_id,
                detection_id=detection_id,
                bucket=bucket
            )

            # Retrieve image from S3
            image_bytes = await self._s3_service.get_file(bucket, key)
            if not image_bytes:
                raise StorageError(f"Image not found: {bucket}/{key}")

            # Detect and extract embeddings for new image
            faces = await self._recognition_service.get_faces_with_embeddings(
                image_bytes,
                max_faces=max_faces
            )

            if not faces:
                logger.warning(
                    "No faces detected in image",
                    key=key,
                    collection_id=collection_id
                )
                return ServiceIndexFacesResponse(
                    face_records=[],
                    detection_id=detection_id,
                    image_key=key
                )

            # Create face records
            face_records = []
            for face in faces:
                face_record = await self._store_face(
                    face=face,
                    collection_id=collection_id,
                    key=key,
                    detection_id=detection_id
                )
                face_records.append(face_record)

            logger.info(
                "Successfully indexed faces",
                collection_id=collection_id,
                faces_count=len(face_records),
                key=key,
                detection_id=detection_id
            )

            return ServiceIndexFacesResponse(
                face_records=face_records,
                detection_id=detection_id,
                image_key=key
            )

        except InvalidImageError as e:
            logger.error(
                "Invalid image format",
                error=str(e),
                key=key
            )
            raise
        except NoFaceDetectedError as e:
            logger.warning(
                "No faces detected in image",
                error=str(e),
                key=key
            )
            raise
        except VectorStoreError as e:
            logger.error(
                "Failed to store faces in vector database",
                error=str(e),
                key=key,
                collection_id=collection_id
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during face indexing",
                error=str(e),
                key=key,
                collection_id=collection_id,
                exc_info=True
            )
            raise VectorStoreError(f"Failed to index faces: {str(e)}")

    def _convert_existing_faces_to_response(
        self,
        existing_faces: List[Face],
        key: str,
        detection_id: str
    ) -> ServiceIndexFacesResponse:
        """Convert existing Face entities to the service response format.

        Args:
            existing_faces: List of domain Face entities retrieved from storage.
            key: S3 object key (path) of the source image.
            detection_id: Original detection operation ID associated with these faces.

        Returns:
            ServiceIndexFacesResponse containing the converted face records.
        """
        face_records = []
        for face in existing_faces:
            try:
                record = ServiceFaceRecord.from_face(
                    face=face,
                    face_id=face.face_id,
                    image_key=key
                )
                face_records.append(record)
            except Exception as e:
                logger.error("Failed to convert Face entity to ServiceFaceRecord", error=str(
                    e), face_details=face, exc_info=True)
                continue

        return ServiceIndexFacesResponse(
            face_records=face_records,
            detection_id=detection_id,
            image_key=key
        )

    async def _store_face(
        self,
        face: Face,
        collection_id: str,
        key: str,
        detection_id: str
    ) -> ServiceFaceRecord:
        """Store face in vector database and return API response record.

        Args:
            face: Face entity with embedding
            collection_id: Collection where face will be stored
            key: S3 object key (path) of the source image
            detection_id: ID grouping faces from same detection operation

        Returns:
            ServiceFaceRecord formatted for API response

        Raises:
            ValueError: If face has no embedding vector
            VectorStoreError: If storing face in vector database fails
        """
        try:
            # Generate a unique ID for this specific face
            face_id = str(uuid.uuid4())

            await self._vector_store.store_face(
                face=face,
                collection_id=collection_id,
                image_key=key,
                face_detection_id=face_id,
                detection_id=detection_id
            )

            logger.debug(
                "Stored face in vector database",
                face_id=face_id,
                detection_id=detection_id,
                collection_id=collection_id,
                key=key
            )

            return ServiceFaceRecord.from_face(
                face=face,
                face_id=face_id,
                image_key=key
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
