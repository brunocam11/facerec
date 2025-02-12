"""API v1 router initialization."""
from fastapi import APIRouter

from .face_recognition import router as face_recognition_router

# Create v1 router
router = APIRouter()

# Include face recognition endpoints
router.include_router(
    face_recognition_router,
    prefix="/face-recognition",
    tags=["face-recognition"]
) 