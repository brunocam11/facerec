"""
Test script for the InsightFace recognition service.

This script demonstrates and verifies the core functionality of the face recognition service.
It includes tests for face detection, embedding extraction, face comparison, and face search.

To run:
    1. Place test images in the tests/data directory
    2. Run with pytest: pytest tests/test_face_recognition.py -v

Note: This is a basic test script. In production, you'd want more comprehensive tests
and proper test fixtures.
"""
import asyncio
from pathlib import Path

import pytest

from app.services import InsightFaceRecognitionService

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "data"


@pytest.mark.asyncio
async def test_face_detection():
    """Test basic face detection functionality."""
    async with InsightFaceRecognitionService() as service:
        # You'll need to add a test image to tests/data/
        image_path = TEST_DATA_DIR / "test_face.jpg"

        # Ensure test image exists
        if not image_path.exists():
            pytest.skip(f"Test image not found at {image_path}")

        # Read test image
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Test face detection
        result = await service.detect_faces(image_bytes)

        # Basic assertions
        assert result is not None
        assert len(result.faces) > 0

        # Check face attributes
        face = result.faces[0]
        assert 0 <= face.confidence <= 100
        assert 0 <= face.bounding_box.top <= 1
        assert 0 <= face.bounding_box.left <= 1
        assert 0 <= face.bounding_box.width <= 1
        assert 0 <= face.bounding_box.height <= 1


@pytest.mark.asyncio
async def test_face_comparison():
    """Test face comparison functionality."""
    async with InsightFaceRecognitionService() as service:
        # You'll need to add test images to tests/data/
        image1_path = TEST_DATA_DIR / "face1.jpg"
        image2_path = TEST_DATA_DIR / "face2.jpg"

        # Skip if test images don't exist
        if not (image1_path.exists() and image2_path.exists()):
            pytest.skip("Test images not found")

        # Read test images
        with open(image1_path, "rb") as f1, open(image2_path, "rb") as f2:
            image1_bytes = f1.read()
            image2_bytes = f2.read()

        # Test face comparison
        result = await service.compare_faces(image1_bytes, image2_bytes)

        # Basic assertions
        assert result is not None
        assert 0 <= result.similarity <= 100
        assert result.source_face is not None
        assert result.target_face is not None


@pytest.mark.asyncio
async def test_face_search():
    """Test face search functionality."""
    async with InsightFaceRecognitionService() as service:
        # You'll need to add test images to tests/data/
        query_image_path = TEST_DATA_DIR / "query_face.jpg"

        if not query_image_path.exists():
            pytest.skip("Test image not found")

        # Read query image
        with open(query_image_path, "rb") as f:
            query_image_bytes = f.read()

        # Create some test embeddings (you would typically load these from your database)
        # Here we'll just extract embeddings from the same image for demonstration
        faces = await service.get_faces_with_embeddings(query_image_bytes)
        test_embeddings = [face.embedding for face in faces]

        # Test face search
        result = await service.search_faces(
            query_image_bytes,
            test_embeddings,
            similarity_threshold=80,
            max_matches=5
        )

        # Basic assertions
        assert result is not None
        assert result.searched_face is not None
        assert len(result.matches) > 0

        # Check that matches are sorted by similarity
        similarities = [match.similarity for match in result.matches]
        assert similarities == sorted(similarities, reverse=True)

if __name__ == "__main__":
    asyncio.run(test_face_detection())
    asyncio.run(test_face_comparison())
    asyncio.run(test_face_search())
