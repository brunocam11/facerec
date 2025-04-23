#!/usr/bin/env python
"""
Index S3 Album Faces

This script indexes faces from images in an S3 album into a Pinecone collection.

Usage:
    python -m app.cli.index_s3_album --bucket <bucket_name> --album <album_id> --collection <collection_id>
"""
import argparse
import asyncio
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import boto3
from tqdm import tqdm

from app.core.config import settings
from app.domain.entities.face import Face
from app.infrastructure.vectordb import PineconeVectorStore
from app.services.recognition.insight_face import InsightFaceRecognitionService


class S3AlbumIndexer:
    """Indexes faces from S3 album images into a collection."""

    def __init__(
        self,
        bucket: str,
        album_id: str,
        collection_id: str,
        prefix: Optional[str] = None,
        max_faces_per_image: int = 5,
        min_face_confidence: float = 0.9,
    ):
        """Initialize the indexer.

        Args:
            bucket: S3 bucket name
            album_id: Album ID
            collection_id: Collection ID to index faces into
            prefix: S3 prefix
            max_faces_per_image: Maximum number of faces to index per image
            min_face_confidence: Minimum confidence for face detection
        """
        self.bucket = bucket
        self.album_id = album_id
        self.collection_id = collection_id
        self.prefix = prefix
        self.max_faces_per_image = max_faces_per_image
        self.min_face_confidence = min_face_confidence
        
        # Initialize services
        self.face_service = InsightFaceRecognitionService()
        self.vector_store = PineconeVectorStore()
        self.s3 = boto3.client('s3')
        
        # Stats
        self.stats = {
            "total_images": 0,
            "processed_images": 0,
            "skipped_images": 0,
            "total_faces": 0,
            "indexed_faces": 0,
            "failed_images": 0,
            "total_time": 0.0,
        }

    def list_images(self) -> List[str]:
        """List images in the album.
        
        Returns:
            List of image keys
        """
        # Construct the prefix for this album
        album_prefix = f"{self.prefix}/{self.album_id}/" if self.prefix else f"{self.album_id}/"
        
        # List objects in the album
        paginator = self.s3.get_paginator('list_objects_v2')
        
        image_keys = []
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=album_prefix):
                for obj in page.get('Contents', []):
                    key = obj.get('Key', '')
                    
                    # Skip if not an image
                    if not key.lower().endswith(('.jpg', '.jpeg', '.png')):
                        continue
                    
                    image_keys.append(key)
        except Exception as e:
            print(f"Error listing images: {e}")
        
        return image_keys

    async def index_image(self, image_key: str) -> Tuple[int, int]:
        """Index faces from an image.
        
        Args:
            image_key: S3 key for the image
            
        Returns:
            Tuple of (number of faces detected, number of faces indexed)
        """
        try:
            # Get image from S3
            response = self.s3.get_object(Bucket=self.bucket, Key=image_key)
            image_bytes = response['Body'].read()
            
            # Detect faces
            faces = await self.face_service.get_faces_with_embeddings(
                image_bytes, 
                max_faces=self.max_faces_per_image
            )
            
            # Filter by confidence
            faces = [face for face in faces if face.confidence >= self.min_face_confidence]
            
            if not faces:
                return 0, 0
            
            # Generate a detection ID for this batch
            detection_id = f"{self.album_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Index each face
            indexed_count = 0
            for i, face in enumerate(faces):
                try:
                    # Generate a unique face ID
                    face_id = f"{os.path.basename(image_key)}_{i}_{uuid.uuid4().hex[:8]}"
                    
                    # Store face in vector database
                    await self.vector_store.store_face(
                        face=face,
                        collection_id=self.collection_id,
                        image_key=image_key,
                        face_id=face_id,
                        detection_id=detection_id,
                    )
                    
                    indexed_count += 1
                except Exception as e:
                    print(f"Error indexing face {i} in {image_key}: {e}")
            
            return len(faces), indexed_count
            
        except Exception as e:
            print(f"Error processing image {image_key}: {e}")
            return 0, 0

    async def index_album(self) -> Dict:
        """Index all images in the album.
        
        Returns:
            Statistics about the indexing process
        """
        # List images
        image_keys = self.list_images()
        self.stats["total_images"] = len(image_keys)
        
        if not image_keys:
            print(f"No images found in album {self.album_id}")
            return self.stats
        
        print(f"Found {len(image_keys)} images in album {self.album_id}")
        
        # Process each image
        start_time = time.time()
        
        for image_key in tqdm(image_keys, desc=f"Indexing {self.album_id}"):
            try:
                faces_detected, faces_indexed = await self.index_image(image_key)
                
                self.stats["processed_images"] += 1
                self.stats["total_faces"] += faces_detected
                self.stats["indexed_faces"] += faces_indexed
                
                if faces_detected == 0:
                    self.stats["skipped_images"] += 1
                
            except Exception as e:
                print(f"Failed to process {image_key}: {e}")
                self.stats["failed_images"] += 1
        
        self.stats["total_time"] = time.time() - start_time
        
        return self.stats

    def print_stats(self) -> None:
        """Print statistics about the indexing process."""
        print("\n===== Indexing Statistics =====")
        print(f"Album: {self.album_id}")
        print(f"Collection: {self.collection_id}")
        print(f"Total images: {self.stats['total_images']}")
        print(f"Processed images: {self.stats['processed_images']}")
        print(f"Skipped images (no faces): {self.stats['skipped_images']}")
        print(f"Failed images: {self.stats['failed_images']}")
        print(f"Total faces detected: {self.stats['total_faces']}")
        print(f"Faces indexed: {self.stats['indexed_faces']}")
        print(f"Total time: {self.stats['total_time']:.2f} seconds")
        
        if self.stats["processed_images"] > 0:
            print(f"Average time per image: {self.stats['total_time'] / self.stats['processed_images']:.2f} seconds")
        
        if self.stats["indexed_faces"] > 0:
            print(f"Average time per face: {self.stats['total_time'] / self.stats['indexed_faces']:.2f} seconds")
        
        print("===============================")


async def main(args):
    """Main entry point."""
    # Create indexer
    indexer = S3AlbumIndexer(
        bucket=args.bucket,
        album_id=args.album,
        collection_id=args.collection,
        prefix=args.prefix,
        max_faces_per_image=args.max_faces,
        min_face_confidence=args.min_confidence,
    )
    
    # Index album
    await indexer.index_album()
    
    # Print stats
    indexer.print_stats()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index faces from S3 album")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--album", required=True, help="Album ID")
    parser.add_argument("--collection", required=True, help="Collection ID")
    parser.add_argument("--prefix", help="S3 prefix")
    parser.add_argument("--max-faces", type=int, default=5, help="Maximum faces per image")
    parser.add_argument("--min-confidence", type=float, default=0.9, help="Minimum face confidence")
    
    args = parser.parse_args()
    
    asyncio.run(main(args)) 