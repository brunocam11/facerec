"""CLI tool for face detection with visualization."""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from app.core.logging import get_logger
from app.services.recognition.insight_face import InsightFaceRecognitionService
from app.domain.entities.face import Face

logger = get_logger(__name__)

def draw_faces(
    image: np.ndarray,
    faces: List[Face],
    output_path: Optional[Path] = None
) -> None:
    """
    Draw bounding boxes and confidence scores on the image.
    
    Args:
        image: Original image as numpy array
        faces: List of detected faces
        output_path: Optional path to save the annotated image
    """
    # Make a copy to avoid modifying the original
    img_draw = image.copy()
    
    # Colors for visualization
    BOX_COLOR = (0, 180, 0)  # Darker green
    TEXT_COLOR = (255, 255, 255)  # White
    
    # Increased font settings
    font_scale = 0.6
    thickness = 3
    
    for i, face in enumerate(faces, 1):
        # Get coordinates (convert from relative to absolute)
        height, width = img_draw.shape[:2]
        bbox = face.bounding_box
        x1 = int(bbox.left * width)
        y1 = int(bbox.top * height)
        x2 = int((bbox.left + bbox.width) * width)
        y2 = int((bbox.top + bbox.height) * height)
        
        # Draw bounding box
        cv2.rectangle(img_draw, (x1, y1), (x2, y2), BOX_COLOR, thickness)
        
        # Draw confidence score
        conf_text = f"Face {i}: {face.confidence:.1f}%"
        
        # Get text size for better positioning
        (text_width, text_height), baseline = cv2.getTextSize(
            conf_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        
        # Draw text background - made slightly larger
        padding = 15  # Increased padding
        cv2.rectangle(
            img_draw,
            (x1, y1 - text_height - padding * 2),
            (x1 + text_width + padding, y1),
            BOX_COLOR,
            -1
        )
        
        # Draw text - adjusted position for new padding
        cv2.putText(
            img_draw,
            conf_text,
            (x1 + padding//2, y1 - padding),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            TEXT_COLOR,
            thickness
        )
    
    # Show the image
    cv2.imshow("Detected Faces", img_draw)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # Save if output path is provided
    if output_path:
        cv2.imwrite(str(output_path), img_draw)
        logger.info("Saved annotated image", path=str(output_path))

async def detect_faces(image_path: str, save_output: bool = True) -> None:
    """
    Detect and visualize faces in the given image.
    
    Args:
        image_path: Path to the image file
        save_output: Whether to save the annotated image
    """
    try:
        # Validate image path
        image_file = Path(image_path)
        if not image_file.exists():
            logger.error("Image file not found", path=image_path)
            sys.exit(1)
            
        # Read image for processing
        with open(image_file, "rb") as f:
            image_bytes = f.read()
        
        # Read image for visualization
        img = cv2.imread(str(image_file))
        if img is None:
            logger.error("Failed to load image for visualization", path=image_path)
            sys.exit(1)
            
        # Process image
        async with InsightFaceRecognitionService() as face_service:
            result = await face_service.detect_faces(image_bytes)
            
        # Print detailed results to command line
        logger.info(
            "Face detection completed",
            num_faces=len(result.faces),
            image_path=image_path
        )
        
        # Print individual face details
        for i, face in enumerate(result.faces, 1):
            logger.info(
                f"Face {i} details",
                confidence=f"{face.confidence:.2f}%",
                position={
                    "top": f"{face.bounding_box.top:.3f}",
                    "left": f"{face.bounding_box.left:.3f}",
                    "width": f"{face.bounding_box.width:.3f}",
                    "height": f"{face.bounding_box.height:.3f}"
                }
            )
        
        # Prepare output path
        output_path = None
        if save_output:
            output_path = image_file.parent / f"{image_file.stem}_detected{image_file.suffix}"
        
        # Draw and display results
        draw_faces(img, result.faces, output_path)
            
    except Exception as e:
        logger.error("Face detection failed", error=str(e), exc_info=True)
        sys.exit(1)

def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Detect and visualize faces in an image")
    parser.add_argument("image_path", help="Path to the image file")
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save the annotated image"
    )
    args = parser.parse_args()
    
    import asyncio
    asyncio.run(detect_faces(args.image_path, not args.no_save))

if __name__ == "__main__":
    main()
