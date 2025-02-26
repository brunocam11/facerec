"""Vector database specific face models."""
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from app.domain.entities.face import Face


class VectorFaceRecord(BaseModel):
    """Face record stored in the vector database (Pinecone)."""
    face_id: str = Field(..., description="Vector database face identifier")
    collection_id: str = Field(..., description="Vector database collection identifier")
    external_image_id: Optional[str] = Field(None, description="Original image identifier")
    confidence: float = Field(..., description="Detection confidence score")
    embedding: np.ndarray = Field(..., description="Face embedding vector for similarity search")

    model_config = ConfigDict(arbitrary_types_allowed=True)  # For numpy array support

    @classmethod
    def from_face(cls, face: Face, face_id: str, collection_id: str, image_id: Optional[str] = None) -> "VectorFaceRecord":
        """Create a vector database record from a face entity.
        
        Args:
            face: Face entity with embedding vector
            face_id: Vector database face identifier
            collection_id: Vector database collection identifier
            image_id: Optional original image identifier
            
        Returns:
            VectorFaceRecord instance for storage in Pinecone
            
        Raises:
            ValueError: If face has no embedding vector
        """
        if face.embedding is None:
            raise ValueError("Face must have an embedding vector for vector database storage")
            
        return cls(
            face_id=face_id,
            collection_id=collection_id,
            external_image_id=image_id,
            confidence=face.confidence,
            embedding=face.embedding
        ) 