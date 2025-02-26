"""Vector database specific models."""
from typing import Optional
from datetime import datetime

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from app.domain.entities.face import Face


class VectorFaceRecord(BaseModel):
    """Face record stored in the vector database (Pinecone).
    
    This model is specific to vector database storage and should only be
    used within the vectordb infrastructure layer.

    Attributes:
        face_id: Unique identifier for this face
        collection_id: Identifier for the collection this face belongs to
        external_image_id: Original image identifier this face was detected in
        detection_id: Identifier grouping all faces detected in the same operation
        confidence: Detection confidence score (0-100)
        embedding: Face embedding vector for similarity search
        bbox_*: Bounding box coordinates normalized to 0-1 range
        created_at: Timestamp when this face was indexed
    """
    face_id: str = Field(..., description="Unique identifier for this face")
    collection_id: str = Field(..., description="Collection identifier")
    external_image_id: Optional[str] = Field(None, description="Original image identifier")
    detection_id: str = Field(..., description="ID grouping faces from same detection operation")
    confidence: float = Field(..., description="Detection confidence score")
    embedding: np.ndarray = Field(..., description="Face embedding vector for similarity search")
    # Bounding box coordinates stored directly
    bbox_left: float = Field(..., description="Left coordinate of the face bounding box")
    bbox_top: float = Field(..., description="Top coordinate of the face bounding box")
    bbox_width: float = Field(..., description="Width of the face bounding box")
    bbox_height: float = Field(..., description="Height of the face bounding box")
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When this face was indexed")

    model_config = ConfigDict(arbitrary_types_allowed=True)  # For numpy array support

    @classmethod
    def from_face(cls, face: Face, face_id: str, collection_id: str, detection_id: str, image_id: Optional[str] = None) -> "VectorFaceRecord":
        """Create a vector database record from a face entity.
        
        Args:
            face: Face entity with embedding vector
            face_id: Unique identifier for this specific face detection
            collection_id: Collection identifier
            detection_id: ID grouping faces from same detection operation
            image_id: Optional original image identifier
            
        Returns:
            VectorFaceRecord instance for storage in Pinecone
            
        Raises:
            ValueError: If face has no embedding vector
        """
        if face.embedding is None:
            raise ValueError("Face must have an embedding vector for vector database storage")
            
        now = datetime.utcnow()
        return cls(
            face_id=face_id,
            collection_id=collection_id,
            external_image_id=image_id,
            detection_id=detection_id,
            confidence=face.confidence,
            embedding=face.embedding,
            bbox_left=face.bounding_box.left,
            bbox_top=face.bounding_box.top,
            bbox_width=face.bounding_box.width,
            bbox_height=face.bounding_box.height,
            created_at=now
        ) 