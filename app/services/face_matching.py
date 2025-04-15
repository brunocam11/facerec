"""Face matching service for finding similar faces in a collection."""
from typing import Optional

from app.core.exceptions import NoFaceDetectedError
from app.core.logging import get_logger
from app.domain.value_objects.recognition import SearchResult
from app.infrastructure.vectordb import PineconeVectorStore
from app.services.recognition.insight_face import InsightFaceRecognitionService

logger = get_logger(__name__)


class FaceMatchingService:
    """Service for matching faces against a collection of indexed faces.
    
    This service uses InsightFace for face detection and embedding extraction,
    and Pinecone for vector similarity search.
    
    Example:
        ```python
        face_service = InsightFaceRecognitionService()
        vector_store = PineconeVectorStore()
        matcher = FaceMatchingService(face_service, vector_store)
        
        with open("query.jpg", "rb") as f:
            image_bytes = f.read()
        
        result = await matcher.match_faces_in_a_collection(
            image_bytes=image_bytes,
            collection_id="my_collection",
            threshold=0.7
        )
        ```
    """

    def __init__(
        self, 
        face_service: InsightFaceRecognitionService, 
        vector_store: PineconeVectorStore
    ) -> None:
        """Initialize the face matching service.

        Args:
            face_service: Service for face detection and embedding extraction
            vector_store: Vector database for storing and searching face embeddings
        """
        self.face_service = face_service
        self.vector_store = vector_store

    async def match_faces_in_a_collection(
        self, 
        image_bytes: bytes, 
        collection_id: str, 
        threshold: float = 0.5
    ) -> SearchResult:
        """Find similar faces in a collection based on a query image.

        This method:
        1. Extracts a single face from the query image
        2. Searches for similar faces in the specified collection
        3. Returns matches above the similarity threshold

        Args:
            image_bytes: Raw bytes of the query image
            collection_id: ID of the collection to search in
            threshold: Minimum similarity score for matches (0.0 to 1.0)

        Returns:
            SearchResult containing:
            - The query face ID
            - List of matching faces with their similarity scores

        Raises:
            NoFaceDetectedError: If no face is detected in the query image
            VectorStoreError: If the vector store search fails
        """
        try:
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
