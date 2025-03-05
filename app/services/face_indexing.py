"""Face indexing service."""
import uuid
from typing import List, Optional

from app.services.models import ServiceFaceRecord, ServiceIndexFacesResponse
from app.core.logging import get_logger
from app.domain.entities import BoundingBox
from app.domain.entities.face import Face
from app.infrastructure.vectordb import PineconeVectorStore
from app.infrastructure.vectordb.models import VectorFaceRecord
from app.services import InsightFaceRecognitionService

logger = get_logger(__name__)


class FaceIndexingService:
    """Service for indexing face operations."""

    def __init__(
        self,
        face_service: InsightFaceRecognitionService,
        vector_store: PineconeVectorStore,
    ):
        """Initialize face indexing service.

        Args:
            face_service: Face recognition service for detection and embeddings
            vector_store: Vector store for face embeddings
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
        """
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
            # Convert vector records to API records
            face_records = []
            for face in existing_faces:
                # Reconstruct bounding box from record
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
                detection_id=detection_id,  # Use the original detection_id
                image_id=image_id
            )

        # Generate new detection_id for new processing
        detection_id = str(uuid.uuid4())

        # Detect and extract embeddings for new image
        faces = await self._face_service.get_faces_with_embeddings(
            image_bytes,
            max_faces=max_faces
        )

        face_records = []
        for face in faces:
            # Store face data and get API response record
            face_record = await self._store_face(
                face=face,
                collection_id=collection_id,
                image_id=image_id,
                detection_id=detection_id  # Pass the detection_id
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
        """
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

        # Create API response record
        return ServiceFaceRecord.from_face(
            face=face,
            face_id=face_id,
            image_id=image_id
        )
