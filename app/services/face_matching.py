"""Face matching service for finding similar faces in a collection."""
from typing import Optional

from app.core.exceptions import NoFaceDetectedError
from app.core.logging import get_logger
from app.domain.value_objects.recognition import SearchResult
from app.infrastructure.vectordb import PineconeVectorStore
from app.services.aws.s3 import S3Service
from app.services.recognition.insight_face import InsightFaceRecognitionService

logger = get_logger(__name__)


class FaceMatchingService:
    """Service for matching faces against a collection of indexed faces.
    
    This service:
    1. Retrieves images from S3
    2. Uses InsightFace for face detection and embedding extraction
    3. Uses Pinecone for vector similarity search
    
    Example:
        ```python
        face_service = InsightFaceRecognitionService()
        vector_store = PineconeVectorStore()
        s3_service = S3Service()
        matcher = FaceMatchingService(face_service, vector_store, s3_service)
        
        result = await matcher.match_faces_in_a_collection(
            bucket="my-bucket",
            key="path/to/query.jpg",
            collection_id="my_collection",
            threshold=0.7
        )
        ```
    """

    def __init__(
        self, 
        face_service: InsightFaceRecognitionService, 
        vector_store: PineconeVectorStore,
        s3_service: S3Service
    ) -> None:
        """Initialize the face matching service.

        Args:
            face_service: Service for face detection and embedding extraction
            vector_store: Vector database for storing and searching face embeddings
            s3_service: S3 service for retrieving images
        """
        self.face_service = face_service
        self.vector_store = vector_store
        self.s3_service = s3_service

    async def match_faces_in_a_collection(
        self, 
        bucket: str,
        key: str,
        collection_id: str, 
        threshold: float = 0.5
    ) -> SearchResult:
        """Find similar faces in a collection based on a query image in S3.

        This method:
        1. Retrieves the query image from S3
        2. Extracts a single face from the query image
        3. Searches for similar faces in the specified collection
        4. Returns matches above the similarity threshold

        Args:
            bucket: S3 bucket containing the query image
            key: S3 object key (path) of the query image
            collection_id: ID of the collection to search in
            threshold: Minimum similarity score for matches (0.0 to 1.0)

        Returns:
            SearchResult containing:
            - The query face ID
            - List of matching faces with their similarity scores

        Raises:
            NoFaceDetectedError: If no face is detected in the query image
            VectorStoreError: If the vector store search fails
            StorageError: If the image cannot be retrieved from S3
        """
        try:
            # Retrieve image from S3
            image_bytes = await self.s3_service.get_file(bucket, key)
            
            faces = await self.face_service.get_faces_with_embeddings(image_bytes, max_faces=1)
            if not faces:
                logger.warning("No faces detected in query image")
                return SearchResult(searched_face_id="", face_matches=[])
                
            # Get the first face from the list of faces (should only be one)
            query_face = faces[0]
            logger.info(
                "Found query face, searching collection",
                collection_id=collection_id,
                threshold=threshold
            )

            # Query the vector store for similar faces
            search_result = await self.vector_store.search_faces(query_face, collection_id, threshold)
            logger.info(
                "Found matches in collection",
                collection_id=collection_id,
                matches_count=len(search_result.face_matches)
            )

            return search_result

        except NoFaceDetectedError:
            logger.error("No face detected in the query image")
            return SearchResult(searched_face_id="", face_matches=[])
        except Exception as e:
            logger.error(
                "Face matching failed",
                error=str(e),
                exc_info=True
            )
            return SearchResult(searched_face_id="", face_matches=[])
