from typing import List

from app.core.exceptions import NoFaceDetectedError
from app.core.logging import get_logger
from app.domain.entities import Face
from app.infrastructure.vectordb import PineconeVectorStore
from app.services.recognition.insight_face import InsightFaceRecognitionService

logger = get_logger(__name__)


class FaceMatchingService:
    def __init__(self, face_service: InsightFaceRecognitionService, vector_store: PineconeVectorStore):
        self.face_service = face_service
        self.vector_store = vector_store

    async def match_faces_in_a_collection(self, image_bytes: bytes, collection_id: str, threshold: float = 0.5) -> List[Face]:
        """
        Given an image, extract just one face and find similar faces in a specific collection on the vector store.

        Args:
            image_bytes: bytes of the image to extract one face from
            collection_id: collection id to search in
            threshold: threshold for similarity

        Returns:
            SearchResult: search result containing the query face and the similar faces
        """
        try:
            faces = await self.face_service.get_faces_with_embeddings(image_bytes, max_faces=1)
            # Get the first face from the list of faces (should only be one)
            query_face = faces[0]

            # Query the vector store for similar faces
            search_result = await self.vector_store.search_faces(query_face, collection_id, threshold)

            return search_result

        except NoFaceDetectedError:
            logger.error(f"No face detected in the image provided")
            return []
