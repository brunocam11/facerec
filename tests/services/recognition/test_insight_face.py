"""Tests for InsightFace recognition service."""
import pytest
from pathlib import Path
from app.services.recognition.insight_face import InsightFaceRecognitionService
import cv2
import numpy as np
from typing import List
from app.domain.entities.face import Face

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"

@pytest.fixture
async def face_service():
    """Provide InsightFace service instance."""
    service = InsightFaceRecognitionService()
    yield service
    await service.__aexit__(None, None, None)

@pytest.fixture
def single_face_image():
    """Load test image with a single face."""
    with open(FIXTURES_DIR / "images/single_face.jpg", "rb") as f:
        return f.read()

@pytest.fixture
def multiple_faces_image():
    """Load test image with multiple faces."""
    with open(FIXTURES_DIR / "images/multiple_faces.jpg", "rb") as f:
        return f.read()

@pytest.fixture
def no_face_image():
    """Load test image without faces."""
    with open(FIXTURES_DIR / "images/no_faces.jpg", "rb") as f:
        return f.read()

def save_detection_visualization(image_bytes: bytes, faces: List[Face], name: str):
    """Save image with detected faces drawn for visual verification."""
    debug_dir = Path(__file__).parent.parent / "debug_output"
    debug_dir.mkdir(exist_ok=True)
    
    # Convert image bytes to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    height, width = img.shape[:2]
    
    # Draw each detected face
    for face in faces:
        # Convert normalized coordinates to pixel coordinates
        left = int(face.bounding_box.left * width)
        top = int(face.bounding_box.top * height)
        right = int((face.bounding_box.left + face.bounding_box.width) * width)
        bottom = int((face.bounding_box.top + face.bounding_box.height) * height)
        
        # Draw rectangle and confidence
        cv2.rectangle(img, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.putText(img, f"{face.confidence:.1f}%", (left, top-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    # Save annotated image
    output_path = debug_dir / f"{name}_detection.jpg"
    cv2.imwrite(str(output_path), img)
    print(f"Detection visualization saved: {output_path}")

class TestInsightFaceRecognition:
    """Test suite for InsightFace recognition service."""

    async def test_detect_single_face(self, face_service, single_face_image):
        """Should detect exactly one face in single face image."""
        result = await face_service.detect_faces(single_face_image)
        
        # Basic detection check
        assert len(result.faces) == 1
        face = result.faces[0]
        
        # Print detection details
        print(f"\nSingle face detection:")
        print(f"Confidence: {face.confidence:.2f}%")
        print(f"Bounding box: left={face.bounding_box.left:.2f}, "
              f"top={face.bounding_box.top:.2f}, "
              f"width={face.bounding_box.width:.2f}, "
              f"height={face.bounding_box.height:.2f}")
        
        # Quality checks
        assert face.confidence > 80, "Face detection confidence should be good"
        
        # Reasonable face size check
        face_area = face.bounding_box.width * face.bounding_box.height
        assert 0.05 < face_area < 0.9, "Face size seems unreasonable"
        
        # Save visualization
        save_detection_visualization(single_face_image, result.faces, "single_face")

    async def test_detect_multiple_faces(self, face_service, multiple_faces_image):
        """Should detect multiple faces in group image."""
        result = await face_service.detect_faces(multiple_faces_image)
        
        # Print detection details
        print(f"\nMultiple faces detection:")
        for i, face in enumerate(result.faces):
            print(f"Face {i+1}:")
            print(f"  Confidence: {face.confidence:.2f}%")
            print(f"  Bounding box: left={face.bounding_box.left:.2f}, "
                  f"top={face.bounding_box.top:.2f}, "
                  f"width={face.bounding_box.width:.2f}, "
                  f"height={face.bounding_box.height:.2f}")
        
        # Basic detection checks
        assert len(result.faces) > 1
        
        # Quality checks
        for face in result.faces:
            assert face.confidence > 75, "All detected faces should have reasonable confidence"
            
            # Check face size
            face_area = face.bounding_box.width * face.bounding_box.height
            assert 0.01 < face_area < 0.5, "Face size seems unreasonable"
        
        # Save visualization
        save_detection_visualization(multiple_faces_image, result.faces, "multiple_faces")

    async def test_no_face_detected(self, face_service, no_face_image):
        """Should handle images without faces."""
        result = await face_service.detect_faces(no_face_image)
        assert len(result.faces) == 0 