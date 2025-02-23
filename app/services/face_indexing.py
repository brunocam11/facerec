"""Face indexing service."""
from dataclasses import dataclass
from typing import List, Optional
import uuid

from app.core.logging import get_logger
from app.domain.entities.face import Face, BoundingBox
from app.domain.value_objects.recognition import FaceMatch, SearchResult
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.infrastructure.storage.pinecone import PineconeVectorStore
from app.services import InsightFaceRecognitionService

logger = get_logger(__name__)


@dataclass
class FaceRecord:
    """Face record returned by face operations."""
    face_id: str
    bounding_box: BoundingBox
    confidence: float
    external_image_id: Optional[str] = None


@dataclass
class IndexingResult:
    """Result of face indexing operation."""
    face_records: List[FaceRecord]
    image_id: str
    external_image_id: Optional[str]


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
        image_bytes: bytes,
        collection_id: str,
        max_faces: int,
        external_image_id: Optional[str],
        uow: UnitOfWork
    ) -> IndexingResult:
        """Index faces from image bytes.
        
        Args:
            image_bytes: Raw image bytes
            collection_id: External collection identifier
            max_faces: Maximum number of faces to index
            external_image_id: Optional external image reference
            uow: Unit of work for database operations
            
        Returns:
            IndexingResult containing the indexed face records
        """
        async with uow.transaction():
            # Get or create collection
            collection = await uow.collections.get_or_create(
                external_id=collection_id
            )
            
            # Detect and extract embeddings
            faces = await self._face_service.get_faces_with_embeddings(
                image_bytes,
                max_faces=max_faces
            )
            
            face_records = []
            for face in faces:
                # Store face data
                face_record = await self._store_face(
                    face=face,
                    collection=collection,
                    external_image_id=external_image_id,
                    uow=uow
                )
                face_records.append(face_record)
            
            logger.info(
                "Successfully indexed faces",
                collection_id=collection_id,
                faces_count=len(face_records)
            )
            
            return IndexingResult(
                face_records=face_records,
                image_id=str(collection.id),
                external_image_id=external_image_id
            )
    
    async def _store_face(
        self,
        face: Face,
        collection: any,  # Collection model
        external_image_id: Optional[str],
        uow: UnitOfWork
    ) -> FaceRecord:
        """Store face in both vector and relational databases.
        
        Args:
            face: Face entity with embedding
            collection: Collection model instance
            external_image_id: Optional external image reference
            uow: Unit of work for database operations
            
        Returns:
            FaceRecord with stored face metadata
        """
        face_detection_id = str(uuid.uuid4())
        
        # Store in vector database
        await self._vector_store.store_face(
            face=face,
            collection_id=collection.external_id,
            image_id=external_image_id,
            face_detection_id=face_detection_id
        )
        
        # Store in relational database
        db_face = await uow.faces.create(
            collection_id=collection.id,
            external_image_id=external_image_id,
            vector_id=face_detection_id,
            confidence=face.confidence,
            bbox_left=face.bounding_box.left,
            bbox_top=face.bounding_box.top,
            bbox_width=face.bounding_box.width,
            bbox_height=face.bounding_box.height
        )
        
        return FaceRecord(
            face_id=str(db_face.id),
            bounding_box=face.bounding_box,
            confidence=face.confidence,
            external_image_id=external_image_id
        ) 