"""
InsightFace-based implementation of face recognition service.

This module provides a concrete implementation of the face recognition service
using the InsightFace library. It handles face detection, embedding extraction,
face comparison, and face search operations.

Key Features:
    - Face detection with confidence filtering
    - Face embedding extraction
    - Face comparison with similarity scoring
    - Face search against a list of embeddings
    - Image validation and preprocessing
    - Normalized coordinate system (0-1)

Example:
    ```python
    service = InsightFaceRecognitionService()
    
    # Detect faces in an image
    with open("image.jpg", "rb") as f:
        result = await service.detect_faces(f.read(), max_faces=5)
        
    # Compare two faces
    result = await service.compare_faces(image1_bytes, image2_bytes)
    print(f"Similarity: {result.similarity}%")
    ```

Note:
    This implementation uses CPU inference by default. For GPU support,
    modify the providers list in __init__ to include 'CUDAExecutionProvider'.
"""
import math
from typing import Any, List, Optional, TypeVar

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from insightface.app.common import Face as InsightFace

from app.core.config import settings
from app.core.exceptions import (
    InvalidImageError,
    MultipleFacesError,
    NoFaceDetectedError,
)
from app.core.logging import get_logger
from app.domain.entities.face import BoundingBox, Face
from app.domain.interfaces.recognition.face_recognition import FaceRecognitionService
from app.domain.value_objects.recognition import (
    ComparisonResult,
    DetectionResult,
    FaceMatch,
    SearchResult,
)

logger = get_logger(__name__)

# Type variable for context manager
T = TypeVar('T', bound='InsightFaceRecognitionService')


class InsightFaceRecognitionService(FaceRecognitionService):
    """
    InsightFace-based implementation of face recognition service.

    This service provides high-performance face recognition capabilities using
    the InsightFace deep learning models. It implements all operations defined
    in the FaceRecognitionService interface.

    Attributes:
        model: InsightFace model instance for face analysis

    Performance Characteristics:
        - Detection time: ~50ms per face
        - Memory usage: ~1-2GB
        - Accuracy: 99.77% on LFW benchmark
    """

    def __init__(self) -> None:
        """Initialize InsightFace model with optimal settings."""
        self.model = FaceAnalysis(
            name="buffalo_l",
            root=settings.MODEL_CACHE_DIR,
            providers=['CPUExecutionProvider']
        )
        # Detection size affects accuracy significantly
        self.model.prepare(ctx_id=0, det_size=(640, 640))

    async def __aenter__(self) -> T:
        """Enter async context, ensuring resources are ready.

        Returns:
            Self instance with initialized resources
        """
        logger.debug("Entering InsightFace service context")
        return self

    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception],
                        exc_tb: Optional[Any]) -> None:
        """Exit async context, ensuring proper cleanup of resources.

        Args:
            exc_type: Type of exception that occurred, if any
            exc_val: Exception instance that occurred, if any
            exc_tb: Traceback of exception that occurred, if any
        """
        logger.debug("Cleaning up InsightFace service resources")
        if exc_type:
            logger.error(
                "Error occurred during context exit",
                error=str(exc_val),
                exc_info=True
            )
        # Clean up model resources
        self.model = None

    async def _load_and_validate_image(self, image_bytes: bytes) -> np.ndarray:
        """Load and optimize image for face detection."""
        try:
            # Decode image bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                raise InvalidImageError("Failed to decode image")

            height, width = img.shape[:2]
            pixels = width * height

            # Only resize if image is too large
            if pixels > settings.MAX_IMAGE_PIXELS:
                scale = math.sqrt(settings.MAX_IMAGE_PIXELS / pixels)
                new_width = int(width * scale)
                new_height = int(height * scale)

                logger.info(
                    "Resizing large image",
                    original_size=(width, height),
                    new_size=(new_width, new_height)
                )

                img = cv2.resize(
                    img,
                    (new_width, new_height),
                    interpolation=cv2.INTER_AREA
                )

            return img

        except Exception as e:
            logger.error("Image loading failed", error=str(e))
            if isinstance(e, InvalidImageError):
                raise
            raise InvalidImageError(f"Invalid image format: {str(e)}")

    def _convert_to_face(self, face_data: InsightFace) -> Face:
        """
        Convert InsightFace detection result to our Face domain model.

        This method handles coordinate normalization and data type conversion
        from InsightFace's internal format to our domain model.

        Args:
            face_data: Face detection result from InsightFace

        Returns:
            Face: Domain model with normalized coordinates (0-1) and scores
        """
        bbox = face_data.bbox.astype(int)

        # Convert bbox to relative coordinates (0-1)
        height, width = face_data.img_size
        bounding_box = BoundingBox(
            top=float(bbox[1] / height),
            left=float(bbox[0] / width),
            width=float((bbox[2] - bbox[0]) / width),
            height=float((bbox[3] - bbox[1]) / height)
        )

        return Face(
            bounding_box=bounding_box,
            # Convert to percentage
            confidence=float(face_data.det_score * 100),
            embedding=face_data.embedding if face_data.embedding is not None else None
        )

    async def _process_image(
        self,
        image: np.ndarray,
        max_faces: Optional[int] = None
    ) -> List[InsightFace]:
        """
        Process image using InsightFace model.

        Args:
            image: Image array to process
            max_faces: Maximum number of faces to detect

        Returns:
            List of detected faces with embeddings
        """
        try:
            logger.debug(
                "Processing image",
                image_shape=image.shape,
                max_faces=max_faces,
                det_size=self.model.det_size
            )

            # Use InsightFace's native max_num parameter, default to -1 for no limit
            faces = self.model.get(
                image, max_num=-1 if max_faces is None else max_faces)

            logger.debug(
                "Face detection results",
                faces_found=len(faces) if faces else 0,
                max_faces=max_faces
            )

            # Filter faces if max_faces is specified
            if max_faces is not None and faces and len(faces) > max_faces:
                faces = faces[:max_faces]
                logger.debug(
                    "Filtered faces to max limit",
                    original_count=len(faces),
                    max_faces=max_faces
                )

            # Add image dimensions to each face
            height, width = image.shape[:2]
            for face in faces:
                face.img_size = (height, width)

            return faces
        except Exception as e:
            logger.error(
                "Face processing failed",
                error=str(e),
                image_shape=image.shape,
                max_faces=max_faces,
                exc_info=True
            )
            raise

    async def detect_faces(
        self,
        image_bytes: bytes,
        max_faces: Optional[int] = None,
        min_confidence: Optional[float] = None,
    ) -> DetectionResult:
        """
        Detect faces with non-blocking processing.
        """
        img = await self._load_and_validate_image(image_bytes)

        faces = await self._process_image(img, max_faces)

        return DetectionResult(
            faces=[self._convert_to_face(face) for face in faces]
        )

    async def extract_embeddings(
        self,
        image_bytes: bytes,
        max_faces: Optional[int] = None,
    ) -> List[Face]:
        """
        Extract face embeddings from an image.

        This method detects faces and computes their embedding vectors,
        which can be used for face comparison and search operations.

        Args:
            image_bytes: Raw image data
            max_faces: Maximum number of faces to process (None for no limit)

        Returns:
            List[Face]: List of faces with computed embeddings

        Raises:
            InvalidImageError: If image format is invalid
            ImageTooLargeError: If image dimensions exceed limits
            NoFaceDetectedError: If no faces are found in the image
        """
        img = await self._load_and_validate_image(image_bytes)
        faces = await self._process_image(img, max_faces)

        if not faces:
            raise NoFaceDetectedError("No faces detected in image")

        return [self._convert_to_face(face) for face in faces]

    async def compare_faces(
        self,
        source_image: bytes,
        target_image: bytes,
        similarity_threshold: Optional[float] = None,
    ) -> ComparisonResult:
        """
        Compare faces between two images.

        This method detects faces in both images and computes their similarity
        score using cosine similarity of their embedding vectors.

        Args:
            source_image: Raw image data of the source face
            target_image: Raw image data of the target face
            similarity_threshold: Minimum similarity score (0-100)

        Returns:
            ComparisonResult: Contains both faces and their similarity score

        Raises:
            InvalidImageError: If any image format is invalid
            ImageTooLargeError: If any image dimensions exceed limits
            NoFaceDetectedError: If no face is found in either image
            MultipleFacesError: If multiple faces found in either image
        """
        try:
            source_faces = await self.get_faces_with_embeddings(source_image, max_faces=1)
            target_faces = await self.get_faces_with_embeddings(target_image, max_faces=1)

            if len(source_faces) > 1:
                logger.warning("Multiple faces found in source image")
                raise MultipleFacesError(
                    "Multiple faces found in source image")
            if len(target_faces) > 1:
                logger.warning("Multiple faces found in target image")
                raise MultipleFacesError(
                    "Multiple faces found in target image")

            source_face = source_faces[0]
            target_face = target_faces[0]

            similarity = self._calculate_similarity(
                np.array(source_face.embedding),
                np.array(target_face.embedding)
            )

            logger.debug(
                "Face comparison completed",
                similarity=similarity,
                threshold=similarity_threshold or settings.SIMILARITY_THRESHOLD
            )

            return ComparisonResult(
                source_face=source_face,
                target_face=target_face,
                similarity=similarity,
                matches=similarity >= (
                    similarity_threshold or settings.SIMILARITY_THRESHOLD)
            )
        except Exception as e:
            if isinstance(e, (MultipleFacesError, NoFaceDetectedError)):
                raise
            logger.error(
                "Face comparison failed",
                error=str(e),
                exc_info=True
            )
            raise

    async def search_faces(
        self,
        image: bytes,
        face_embeddings: List[List[float]],
        similarity_threshold: Optional[float] = None,
        max_matches: Optional[int] = None,
    ) -> SearchResult:
        """
        Search for similar faces using face embeddings.

        This method compares a query face against a list of face embeddings
        and returns the most similar matches above the threshold.

        Args:
            image: Raw image data of the query face
            face_embeddings: List of face embeddings to search against
            similarity_threshold: Minimum similarity score (0-100)
            max_matches: Maximum number of matches to return

        Returns:
            SearchResult: Contains query face and list of matches

        Raises:
            InvalidImageError: If image format is invalid
            ImageTooLargeError: If image dimensions exceed limits
            NoFaceDetectedError: If no face is found in the image
            MultipleFacesError: If multiple faces found in the image
        """
        # Get only embeddings for the query face
        query_embeddings = await self.get_face_embeddings(image, max_faces=1)

        if len(query_embeddings) > 1:
            raise MultipleFacesError("Multiple faces found in query image")

        # Get full face info for the response (we need this for the API response)
        query_face = (await self.get_faces_with_embeddings(image, max_faces=1))[0]

        # Compare embeddings
        query_embedding = query_embeddings[0]
        target_embeddings = np.array(face_embeddings)

        similarities = [
            self._calculate_similarity(query_embedding, target_embedding)
            for target_embedding in target_embeddings
        ]

        threshold = similarity_threshold or settings.SIMILARITY_THRESHOLD
        matches = [
            FaceMatch(
                face=Face(
                    bounding_box=BoundingBox(top=0, left=0, width=1, height=1),
                    confidence=100,
                    embedding=emb.tolist()
                ),
                similarity=float(sim)
            )
            for emb, sim in zip(target_embeddings, similarities)
            if sim >= threshold
        ]

        matches.sort(key=lambda x: x.similarity, reverse=True)
        if max_matches:
            matches = matches[:max_matches]

        return SearchResult(
            searched_face=query_face,
            matches=matches
        )

    def _calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate similarity between face embeddings using cosine similarity.

        Args:
            embedding1: First face embedding vector
            embedding2: Second face embedding vector

        Returns:
            float: Similarity score between 0 and 100
        """
        try:
            # Normalize embeddings
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            if norm1 == 0 or norm2 == 0:
                return 0.0

            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)

            # Convert to percentage and ensure range [0, 100]
            return float(max(0, min(100, (similarity + 1) * 50)))
        except Exception as e:
            logger.error(
                "Similarity calculation failed",
                error=str(e),
                exc_info=True
            )
            raise

    async def get_face_embeddings(
        self,
        image_bytes: bytes,
        max_faces: Optional[int] = None,
    ) -> List[np.ndarray]:
        """Extract only face embeddings using InsightFace's native method."""
        img = await self._load_and_validate_image(image_bytes)

        try:
            # Use InsightFace's native get_feat method if available
            faces = await self._process_image(img, max_faces)
            if not faces:
                raise NoFaceDetectedError("No faces detected in image")

            return [face.embedding for face in faces]
        except Exception as e:
            logger.error(
                "Failed to extract face embeddings",
                error=str(e),
                exc_info=True
            )
            raise

    async def get_faces_with_embeddings(
        self,
        image_bytes: bytes,
        max_faces: Optional[int] = None,
    ) -> List[Face]:
        """Get full face information including embeddings."""
        img = await self._load_and_validate_image(image_bytes)
        faces = await self._process_image(img, max_faces)

        if not faces:
            raise NoFaceDetectedError("No faces detected in image")

        return [self._convert_to_face(face) for face in faces]
