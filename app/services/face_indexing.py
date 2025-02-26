"""Face indexing service."""
import uuid
from typing import List, Optional

from app.core.logging import get_logger
from app.domain.entities.face import Face
from app.api.models.face import FaceRecord, IndexFacesResponse
from app.infrastructure.vectordb.models import VectorFaceRecord
from app.infrastructure.vectordb import PineconeVectorStore
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
    ) -> IndexFacesResponse:
        """Index faces from image bytes.

        Args:
            image_id: Source image identifier
            image_bytes: Raw image bytes
            collection_id: Collection where faces will be stored
            max_faces: Optional maximum number of faces to index

        Returns:
            IndexFacesResponse containing the indexed face records
        """
        # Detect and extract embeddings
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
                image_id=image_id
            )
            face_records.append(face_record)

        logger.info(
            "Successfully indexed faces",
            collection_id=collection_id,
            faces_count=len(face_records)
        )

        detection_id = str(uuid.uuid4())
        return IndexFacesResponse(
            face_records=face_records,
            detection_id=detection_id,
            image_id=image_id
        )

    async def _store_face(
        self,
        face: Face,
        collection_id: str,
        image_id: Optional[str]
    ) -> FaceRecord:
        """Store face in vector database and return API response record.

        Args:
            face: Face entity with embedding
            collection_id: Collection where face will be stored
            image_id: Source image identifier

        Returns:
            FaceRecord formatted for API response
            
        Raises:
            ValueError: If face has no embedding vector
        """
        face_detection_id = str(uuid.uuid4())

        # Create vector database record
        vector_record = VectorFaceRecord.from_face(
            face=face,
            face_id=face_detection_id,
            collection_id=collection_id,
            image_id=image_id
        )

        # Store in vector database
        await self._vector_store.store_face(
            face=face,
            collection_id=collection_id,
            image_id=image_id,
            face_detection_id=face_detection_id
        )

        # Create API response record
        return FaceRecord.from_face(
            face=face,
            face_id=face_detection_id,
            image_id=image_id
        )
