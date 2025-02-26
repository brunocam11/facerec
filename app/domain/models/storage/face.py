"""Storage-specific face models."""
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

from app.domain.entities.face import Face


class StoredFaceRecord(BaseModel):
    """Face record stored in the vector database."""
    face_id: str = Field(..., description="External system face identifier")
    collection_id: str = Field(..., description="External system collection identifier")
    external_image_id: Optional[str] = Field(None, description="External system image identifier")
    confidence: float = Field(..., description="Confidence score of the detection")
    embedding: np.ndarray = Field(..., description="Face embedding vector")

    class Config:
        arbitrary_types_allowed = True  # Allow numpy array

    @classmethod
    def from_face(cls, face: Face, face_id: str, collection_id: str, image_id: Optional[str] = None) -> "StoredFaceRecord":
        """Create a storage record from a face entity.
        
        Args:
            face: Face entity with embedding
            face_id: External system face identifier
            collection_id: External system collection identifier
            image_id: Optional external system image identifier
            
        Returns:
            StoredFaceRecord instance
        """
        return cls(
            face_id=face_id,
            collection_id=collection_id,
            external_image_id=image_id,
            confidence=face.confidence,
            embedding=face.embedding
        ) 