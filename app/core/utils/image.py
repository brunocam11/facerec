"""
Image processing utility functions.
"""
import numpy as np
import cv2
from typing import Union, Tuple, Optional

def bytes_to_numpy_array(image_bytes: bytes, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
    """Convert image bytes to a numpy array.
    
    Args:
        image_bytes: Raw image bytes
        flags: OpenCV imread flags (default: COLOR)
        
    Returns:
        numpy.ndarray: Image as a numpy array
        
    Raises:
        ValueError: If the image cannot be decoded
    """
    # Convert bytes to numpy array
    np_array = np.frombuffer(image_bytes, np.uint8)
    
    # Decode the image
    img = cv2.imdecode(np_array, flags)
    
    if img is None:
        raise ValueError("Failed to decode image bytes")
        
    return img 