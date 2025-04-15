#!/usr/bin/env python
"""
CLI script to test face recognition API by sending an image and displaying matched faces.
"""
import argparse
import json
import logging
import os
import sys
from typing import List, Optional
from urllib.parse import urljoin

import requests
from PIL import Image
from io import BytesIO

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, project_root)

from app.core.config import settings
from app.services.aws.s3 import S3Service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_presigned_url(s3_service: S3Service, image_id: str, collection_id: str) -> str:
    """Get a pre-signed URL for an image ID using S3Service."""
    try:
        # Construct the S3 key with collection_id prefix
        s3_key = f"{collection_id}/{image_id}"
        url = await s3_service.get_file_url(s3_key)
        return url
    except Exception as e:
        logger.error(f"Failed to get pre-signed URL for image {image_id}: {str(e)}")
        return None


def download_image(url: str) -> Optional[Image.Image]:
    """Download an image from URL and return as PIL Image."""
    if not url:
        return None
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {str(e)}")
        return None


async def create_grid_image(query_image: Image.Image, matches: List[dict], s3_service: S3Service, collection_id: str, output_dir: str):
    """Create a grid of images using PIL."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate grid size
    n_matches = len(matches)
    n_cols = min(3, n_matches)  # Max 3 columns
    n_rows = (n_matches + n_cols - 1) // n_cols
    
    # Calculate cell size based on query image
    cell_width = query_image.width
    cell_height = query_image.height
    
    # Create a new image with the grid
    grid_width = cell_width * n_cols
    grid_height = cell_height * n_rows
    grid_image = Image.new('RGB', (grid_width, grid_height))
    
    # Paste query image
    grid_image.paste(query_image, (0, 0))
    
    # Paste matches
    for i, match in enumerate(matches):
        row = i // n_cols
        col = i % n_cols
        presigned_url = await get_presigned_url(s3_service, match['image_id'], collection_id)
        img = download_image(presigned_url)
        if img:
            # Resize to match cell size
            img = img.resize((cell_width, cell_height))
            grid_image.paste(img, (col * cell_width, row * cell_height))
    
    # Save the grid
    output_path = os.path.join(output_dir, "face_matches.png")
    grid_image.save(output_path, quality=95)
    logger.info(f"Saved results to {output_path}")


async def test_face_recognition(
    api_url: str,
    image_path: str,
    collection_id: str,
    output_dir: str = "test_results"
) -> None:
    """
    Test face recognition API with a given image.
    
    Args:
        api_url: API endpoint URL
        image_path: Path to the query image
        collection_id: Collection ID to search in
        output_dir: Directory to save results
    """
    try:
        # Initialize S3 service
        s3_service = S3Service()
        await s3_service.initialize()
        
        # Read image file
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Prepare request
        files = {'image': ('image.jpg', image_data, 'image/jpeg')}
        data = {
            'collection_id': collection_id,
            'threshold': 0.8  # Add similarity threshold
        }
        
        # Send request
        match_url = urljoin(api_url, "/api/v1/face-recognition/faces/match")
        logger.info(f"Sending request to {match_url}")
        response = requests.post(match_url, data=data, files=files)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"API Response: {json.dumps(result, indent=2)}")
        
        # Check if we have matches
        if not result.get('face_matches'):
            logger.warning("No face matches found")
            return
        
        # Display results
        query_image = Image.open(image_path)
        await create_grid_image(query_image, result['face_matches'], s3_service, collection_id, output_dir)
        
        # Log matches
        logger.info(f"Found {len(result['face_matches'])} matches:")
        for i, match in enumerate(result['face_matches'], 1):
            logger.info(
                f"Match {i}: Score={match['similarity']:.2f}, "
                f"ID={match['face_id']}, "
                f"Image={match['image_id']}"
            )
        
        # Cleanup
        await s3_service.cleanup()
        
    except Exception as e:
        logger.error(f"Error testing face recognition: {str(e)}")
        raise


async def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Test face recognition API')
    parser.add_argument('--api-url', type=str, required=True, help='API endpoint URL')
    parser.add_argument('--image', type=str, required=True, help='Path to query image')
    parser.add_argument('--collection-id', type=str, required=True, help='Collection ID to search in')
    parser.add_argument('--output-dir', type=str, default='test_results', help='Directory to save results')
    
    args = parser.parse_args()
    
    # Show startup information
    logger.info("=" * 40)
    logger.info("Starting face recognition test")
    logger.info(f"API URL: {args.api_url}")
    logger.info(f"Query image: {args.image}")
    logger.info(f"Collection ID: {args.collection_id}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info("=" * 40)
    
    try:
        await test_face_recognition(
            api_url=args.api_url,
            image_path=args.image,
            collection_id=args.collection_id,
            output_dir=args.output_dir
        )
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 