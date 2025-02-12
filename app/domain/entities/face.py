"""Face domain entities."""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import numpy as np
from pydantic import BaseModel


class BoundingBox(BaseModel):
    """Face bounding box coordinates."""
    left: float
    top: float
    width: float
    height: float


@dataclass
class Face:
    """Face detection result with optional embedding."""
    confidence: float
    bounding_box: BoundingBox
    embedding: Optional[np.ndarray] = None


@dataclass
class FaceRecord:
    """Face record stored in the system."""
    face_id: UUID
    collection_id: UUID
    external_image_id: Optional[str]
    confidence: float
    embedding: np.ndarray 