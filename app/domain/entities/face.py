"""Core face domain entities."""
from typing import Optional, Union

import numpy as np
from pydantic import BaseModel, Field, field_validator, ConfigDict


class BoundingBox(BaseModel):
    """Face bounding box coordinates."""
    left: float = Field(..., description="Left coordinate of the bounding box")
    top: float = Field(..., description="Top coordinate of the bounding box")
    width: float = Field(..., description="Width of the bounding box")
    height: float = Field(..., description="Height of the bounding box")


class Face(BaseModel):
    """Face detection result with optional embedding."""
    confidence: float = Field(..., description="Confidence score of the detection")
    bounding_box: BoundingBox = Field(..., description="Bounding box coordinates")
    embedding: Optional[np.ndarray] = Field(None, description="Face embedding vector")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('embedding')
    @classmethod
    def validate_embedding(cls, v: Optional[Union[np.ndarray, list]]) -> Optional[np.ndarray]:
        """Validate and convert embedding to numpy array if needed."""
        if v is None:
            return None
        if isinstance(v, list):
            return np.array(v)
        return v