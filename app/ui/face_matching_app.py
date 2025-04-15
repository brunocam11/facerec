#!/usr/bin/env python
"""
Face Matching Streamlit App

A simple Streamlit application for testing face matching accuracy by:
1. Uploading a query face or selecting from S3
2. Matching against faces in a collection
3. Visualizing the results
4. Indexing S3 albums into collections

Usage:
    streamlit run app/ui/face_matching_app.py
"""
import asyncio
import concurrent.futures
import io
import json
import os
import tempfile
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set

import boto3
import cv2
import numpy as np
import streamlit as st
from PIL import Image

from app.core.config import settings
from app.domain.entities.face import Face
from app.domain.value_objects.recognition import FaceMatch, SearchResult
from app.infrastructure.vectordb import PineconeVectorStore
from app.services.recognition.insight_face import InsightFaceRecognitionService
from app.services.face_indexing import FaceIndexingService
from app.services.face_matching import FaceMatchingService


# Initialize services
@st.cache_resource
def get_face_service():
    """Get face recognition service."""
    return InsightFaceRecognitionService()


@st.cache_resource
def get_vector_store():
    """Get vector store."""
    return PineconeVectorStore()


@st.cache_resource
def get_s3_client():
    """Get S3 client."""
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )


@st.cache_resource
def get_face_indexing_service():
    """Get face indexing service."""
    return FaceIndexingService(
        face_service=get_face_service(),
        vector_store=get_vector_store()
    )


@st.cache_resource
def get_face_matching_service():
    """Get face matching service."""
    return FaceMatchingService(
        face_service=get_face_service(),
        vector_store=get_vector_store()
    )


# Persistent state management
def load_indexed_images() -> Dict[str, Set[str]]:
    """Load indexed images from persistent storage.
    
    Returns:
        Dictionary mapping collection IDs to sets of indexed image keys
    """
    try:
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        # Try to load existing data
        if os.path.exists('data/indexed_images.json'):
            with open('data/indexed_images.json', 'r') as f:
                data = json.load(f)
                
            # Convert lists back to sets
            return {k: set(v) for k, v in data.items()}
        
    except Exception as e:
        st.warning(f"Could not load indexed images data: {e}")
    
    return {}


def save_indexed_images(indexed_images: Dict[str, Set[str]]) -> None:
    """Save indexed images to persistent storage.
    
    Args:
        indexed_images: Dictionary mapping collection IDs to sets of indexed image keys
    """
    try:
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        # Convert sets to lists for JSON serialization
        serializable_data = {k: list(v) for k, v in indexed_images.items()}
        
        # Save to file
        with open('data/indexed_images.json', 'w') as f:
            json.dump(serializable_data, f)
            
    except Exception as e:
        st.warning(f"Could not save indexed images data: {e}")


# Helper functions
async def detect_faces(image_bytes: bytes) -> List[Face]:
    """Detect faces in an image.
    
    Args:
        image_bytes: Image bytes
        
    Returns:
        List of detected faces
    """
    face_service = get_face_service()
    return await face_service.get_faces_with_embeddings(image_bytes, max_faces=1)


async def match_face_to_collection(image_bytes: bytes, collection_id: str, threshold: float) -> SearchResult:
    """Match a face to a collection using the face matching service.
    
    Args:
        image_bytes: Image bytes containing a face
        collection_id: Collection ID
        threshold: Similarity threshold
        
    Returns:
        Search result
    """
    face_matching_service = get_face_matching_service()
    return await face_matching_service.match_faces_in_a_collection(
        image_bytes=image_bytes,
        collection_id=collection_id,
        threshold=threshold
    )


async def index_image(image_key: str, image_bytes: bytes, collection_id: str, max_faces: int) -> Tuple[int, int]:
    """Index faces from an image using the face indexing service.
    
    Args:
        image_key: S3 key for the image
        image_bytes: Image bytes
        collection_id: Collection ID
        max_faces: Maximum number of faces to index
        
    Returns:
        Tuple of (number of faces detected, number of faces indexed)
    """
    try:
        face_indexing_service = get_face_indexing_service()
        result = await face_indexing_service.index_faces(
            image_id=image_key,
            image_bytes=image_bytes,
            collection_id=collection_id,
            max_faces=max_faces
        )
        
        return len(result.face_records), len(result.face_records)
    except Exception as e:
        st.error(f"Error indexing image {os.path.basename(image_key)}: {e}")
        return 0, 0


def get_image_from_s3(bucket: str, key: str) -> bytes:
    """Get image from S3.
    
    Args:
        bucket: S3 bucket
        key: S3 key
        
    Returns:
        Image bytes
    """
    s3 = get_s3_client()
    response = s3.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()


def list_s3_albums(bucket: str, prefix: str = "") -> List[str]:
    """List albums in S3 bucket.
    
    Args:
        bucket: S3 bucket
        prefix: S3 prefix
        
    Returns:
        List of album IDs
    """
    s3 = get_s3_client()
    
    # Use a delimiter to get "directories"
    delimiter = '/'
    prefix = f"{prefix}/" if prefix else ""
    
    # Get unique prefixes (albums)
    album_ids = set()
    paginator = s3.get_paginator('list_objects_v2')
    
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter=delimiter):
            for prefix_dict in page.get('CommonPrefixes', []):
                # Extract album ID from prefix
                album_prefix = prefix_dict.get('Prefix', '')
                album_id = album_prefix.rstrip('/').split('/')[-1]
                album_ids.add(album_id)
    except Exception as e:
        st.error(f"Error listing albums: {e}")
    
    return sorted(list(album_ids))


def list_s3_images(bucket: str, album_id: str, prefix: str = "", limit: int = 10) -> List[str]:
    """List images in an S3 album.
    
    Args:
        bucket: S3 bucket
        album_id: Album ID
        prefix: S3 prefix
        limit: Maximum number of images to return
        
    Returns:
        List of image keys
    """
    s3 = get_s3_client()
    
    # Construct the prefix for this album
    album_prefix = f"{prefix}/{album_id}/" if prefix else f"{album_id}/"
    
    # List objects in the album
    paginator = s3.get_paginator('list_objects_v2')
    
    image_keys = []
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=album_prefix):
            for obj in page.get('Contents', []):
                key = obj.get('Key', '')
                
                # Skip if not an image
                if not key.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue
                
                image_keys.append(key)
                
                if len(image_keys) >= limit:
                    break
            
            if len(image_keys) >= limit:
                break
    except Exception as e:
        st.error(f"Error listing images: {e}")
    
    return image_keys


def draw_face_box(image: np.ndarray, face: Face, color: Tuple[int, int, int] = (0, 255, 0), thickness: int = 2) -> np.ndarray:
    """Draw a bounding box around a face.
    
    Args:
        image: Image as numpy array
        face: Face object
        color: Box color (BGR)
        thickness: Line thickness
        
    Returns:
        Image with bounding box
    """
    # Get image dimensions
    height, width = image.shape[:2]
    
    # Get bounding box coordinates
    bbox = face.bounding_box
    left = int(bbox.left * width)
    top = int(bbox.top * height)
    right = int((bbox.left + bbox.width) * width)
    bottom = int((bbox.top + bbox.height) * height)
    
    # Draw rectangle
    cv2.rectangle(image, (left, top), (right, bottom), color, thickness)
    
    # Add confidence score
    confidence_text = f"{face.confidence:.2f}"
    cv2.putText(image, confidence_text, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, thickness)
    
    return image


def create_match_visualization(query_image: np.ndarray, match_images: List[Tuple[np.ndarray, float, bool]]) -> np.ndarray:
    """Create a visualization of matches.
    
    Args:
        query_image: Query image
        match_images: List of (image, similarity, is_match) tuples
        
    Returns:
        Visualization image
    """
    # Resize query image
    max_height = 300
    height, width = query_image.shape[:2]
    scale = max_height / height
    query_image = cv2.resize(query_image, (int(width * scale), max_height))
    
    # Resize match images
    resized_matches = []
    for img, similarity, is_match in match_images:
        height, width = img.shape[:2]
        scale = max_height / height
        resized = cv2.resize(img, (int(width * scale), max_height))
        resized_matches.append((resized, similarity, is_match))
    
    # Create canvas
    max_width = max([query_image.shape[1]] + [img.shape[1] for img, _, _ in resized_matches])
    canvas_height = max_height * (len(resized_matches) + 1)
    canvas_width = max_width
    canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255
    
    # Add query image
    y_offset = 0
    x_offset = (canvas_width - query_image.shape[1]) // 2
    canvas[y_offset:y_offset + query_image.shape[0], x_offset:x_offset + query_image.shape[1]] = query_image
    
    return canvas


# Main app
def main():
    st.set_page_config(
        page_title="Face Matching Tester",
        page_icon="👤",
        layout="wide"
    )
    
    # Initialize session state for indexing control
    if 'indexing_running' not in st.session_state:
        st.session_state.indexing_running = False
    
    # Load indexed images from persistent storage
    if 'indexed_images_dict' not in st.session_state:
        st.session_state.indexed_images_dict = load_indexed_images()
    
    st.title("Face Matching Tester")
    
    # Create tabs for different functionalities
    tab1, tab2 = st.tabs(["Face Matching", "Index S3 Album"])
    
    with tab1:
        st.write("Upload a face image or select from S3 to test face matching against a collection.")
        
        # Sidebar
        st.sidebar.title("Settings")
        
        # S3 settings
        s3_bucket = st.sidebar.text_input("S3 Bucket", settings.AWS_S3_BUCKET)
        s3_prefix = st.sidebar.text_input("S3 Prefix", "")
        
        # Collection settings
        collection_id = st.sidebar.text_input("Collection ID", "test_collection")
        
        # Matching settings
        threshold = st.sidebar.slider("Similarity Threshold", 0.0, 1.0, 0.7, 0.01)
        max_matches = st.sidebar.slider("Max Matches", 1, 20, 5)
        
        # Main content
        col1, col2 = st.columns(2)
        
        with col1:
            st.header("Query Face")
            
            # Option to upload image or select from S3
            query_option = st.radio("Select query image from:", ["Upload", "S3"])
            
            query_image_bytes = None
            
            if query_option == "Upload":
                uploaded_file = st.file_uploader("Upload a face image", type=["jpg", "jpeg", "png"])
                
                if uploaded_file is not None:
                    query_image_bytes = uploaded_file.read()
                    st.image(query_image_bytes, caption="Uploaded Image", use_container_width=True)
            else:
                # List albums
                albums = list_s3_albums(s3_bucket, s3_prefix)
                selected_album = st.selectbox("Select Album", albums)
                
                if selected_album:
                    # List images
                    images = list_s3_images(s3_bucket, selected_album, s3_prefix)
                    image_options = [os.path.basename(key) for key in images]
                    
                    selected_image_idx = st.selectbox("Select Image", range(len(image_options)), format_func=lambda x: image_options[x])
                    
                    if selected_image_idx is not None:
                        selected_image_key = images[selected_image_idx]
                        
                        try:
                            query_image_bytes = get_image_from_s3(s3_bucket, selected_image_key)
                            st.image(query_image_bytes, caption=f"Selected Image: {os.path.basename(selected_image_key)}", use_container_width=True)
                        except Exception as e:
                            st.error(f"Error loading image: {e}")
        
        with col2:
            st.header("Match Results")
            
            if query_image_bytes is not None:
                if st.button("Run Face Matching"):
                    with st.spinner("Processing..."):
                        # Convert to numpy array for OpenCV
                        nparr = np.frombuffer(query_image_bytes, np.uint8)
                        query_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        query_img_rgb = cv2.cvtColor(query_img, cv2.COLOR_BGR2RGB)
                        
                        # Match to collection using the face matching service
                        start_time = time.time()
                        result = asyncio.run(match_face_to_collection(
                            image_bytes=query_image_bytes,
                            collection_id=collection_id,
                            threshold=threshold
                        ))
                        query_time = time.time() - start_time
                        
                        # Display results
                        st.write(f"Query completed in {query_time:.4f} seconds")
                        
                        if not result.face_matches:
                            st.info("No matches found.")
                        else:
                            st.success(f"Found {len(result.face_matches)} matches.")
                            
                            # Display matches
                            match_images = []
                            
                            for i, match in enumerate(result.face_matches[:max_matches]):
                                st.write(f"Match {i+1}: {match.face_id} (Similarity: {match.similarity:.2f})")
                                
                                try:
                                    # Get match image from S3
                                    match_image_bytes = get_image_from_s3(s3_bucket, match.image_id)
                                    
                                    # Convert to numpy array
                                    nparr = np.frombuffer(match_image_bytes, np.uint8)
                                    match_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                                    match_img_rgb = cv2.cvtColor(match_img, cv2.COLOR_BGR2RGB)
                                    
                                    # Add to match images
                                    match_images.append((match_img_rgb, match.similarity, True))
                                    
                                    # Display match image with a more descriptive caption
                                    image_filename = os.path.basename(match.image_id)
                                    st.image(match_img_rgb, caption=f"Match {i+1}: {image_filename} ({match.similarity:.2f})", width=300)
                                except Exception as e:
                                    st.error(f"Error loading match image: {e}")
                                    # Log more details to help debug
                                    st.info(f"Image ID from Pinecone: {match.image_id}")
                                    st.info(f"Attempted S3 path: s3://{s3_bucket}/{match.image_id}")
                            
                            # Create visualization
                            if match_images:
                                visualization = create_match_visualization(query_img_rgb, match_images)
                                visualization_rgb = cv2.cvtColor(visualization, cv2.COLOR_BGR2RGB)
                                st.image(visualization_rgb, caption="Match Visualization", use_container_width=True)
    
    with tab2:
        st.header("Index S3 Album")
        st.write("Index faces from an S3 album into a collection for face matching.")
        
        # S3 settings
        s3_bucket = st.text_input("S3 Bucket", settings.AWS_S3_BUCKET, key="index_bucket")
        s3_prefix = st.text_input("S3 Prefix", "", key="index_prefix")
        
        # List albums
        albums = list_s3_albums(s3_bucket, s3_prefix)
        selected_album = st.selectbox("Select Album to Index", albums, key="index_album")
        
        # Collection settings - use album ID as collection ID by default
        collection_id = st.text_input("Collection ID", selected_album if selected_album else "test_collection", key="index_collection")
        
        # Get indexed images for this collection
        if collection_id not in st.session_state.indexed_images_dict:
            st.session_state.indexed_images_dict[collection_id] = set()
        
        indexed_images = st.session_state.indexed_images_dict[collection_id]
        
        # Show indexing progress
        if indexed_images:
            st.info(f"Found {len(indexed_images)} previously indexed images in this collection.")
        
        # Indexing settings
        col1, col2 = st.columns(2)
        with col1:
            max_faces = st.slider("Max Faces per Image", 1, 10, 5)
        with col2:
            min_confidence = st.slider("Min Face Confidence", 0.5, 1.0, 0.9, 0.01)
            
        # Parallel processing settings
        max_workers = st.slider("Parallel Workers", 1, 10, 4, 
                               help="Number of parallel workers for indexing. Higher values may improve performance but use more resources.")
        
        # Quick resume options
        st.subheader("Resume Options")
        resume_method = st.radio(
            "Resume Method",
            ["Auto (Use Saved Progress)", "Start from Position", "Reset (Start from Beginning)"],
            help="Choose how to resume indexing"
        )
        
        start_position = 0
        if resume_method == "Start from Position":
            start_position = st.number_input(
                "Start from Position", 
                min_value=0, 
                value=0,
                help="Enter the position in the album to start indexing from (0-based index)"
            )
        elif resume_method == "Reset (Start from Beginning)":
            if st.button("Confirm Reset"):
                if collection_id in st.session_state.indexed_images_dict:
                    st.session_state.indexed_images_dict[collection_id] = set()
                    save_indexed_images(st.session_state.indexed_images_dict)
                    st.success("Indexing progress has been reset.")
                    st.experimental_rerun()
        
        # Preview images
        if selected_album:
            st.subheader("Album Preview")
            preview_images = list_s3_images(s3_bucket, selected_album, s3_prefix, limit=5)
            
            if preview_images:
                st.write(f"Found {len(preview_images)} images in album. Showing first 5:")
                
                # Display preview images in a grid
                cols = st.columns(min(5, len(preview_images)))
                for i, image_key in enumerate(preview_images[:5]):
                    try:
                        image_bytes = get_image_from_s3(s3_bucket, image_key)
                        cols[i].image(image_bytes, caption=os.path.basename(image_key), use_container_width=True)
                    except Exception as e:
                        cols[i].error(f"Error loading preview: {e}")
            else:
                st.warning("No images found in this album.")
        
        # Index button and stop button
        col1, col2 = st.columns(2)
        
        with col1:
            start_button = st.button("Index Album", disabled=st.session_state.indexing_running)
        
        with col2:
            stop_button = st.button("Stop Indexing", disabled=not st.session_state.indexing_running)
            
        if stop_button:
            st.session_state.indexing_running = False
            st.warning("Indexing stopped by user.")
            # Save progress when stopped
            save_indexed_images(st.session_state.indexed_images_dict)
        
        # Status area
        status_container = st.container()
        
        # Index album when button is clicked
        if start_button:
            if not selected_album:
                st.error("Please select an album to index.")
            else:
                # Set indexing state to running
                st.session_state.indexing_running = True
                
                # Get all images in the album
                all_images = list_s3_images(s3_bucket, selected_album, s3_prefix, limit=1000)
                
                if not all_images:
                    st.error("No images found in the selected album.")
                    st.session_state.indexing_running = False
                else:
                    # Create progress bar and status text in the status container
                    with status_container:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        stats_text = st.empty()
                        
                        # Stats
                        stats = {
                            "total_images": len(all_images),
                            "processed_images": 0,
                            "skipped_images": 0,
                            "total_faces": 0,
                            "indexed_faces": 0,
                            "failed_images": 0,
                            "already_indexed": len(indexed_images) if resume_method == "Auto (Use Saved Progress)" else 0,
                        }
                        
                        # Process each image
                        start_time = time.time()
                        
                        # Determine images to process based on resume method
                        if resume_method == "Auto (Use Saved Progress)":
                            # Filter out already indexed images
                            images_to_process = [img for img in all_images if img not in indexed_images]
                            status_message = f"Indexing {len(images_to_process)} images (skipping {stats['already_indexed']} already indexed)..."
                        elif resume_method == "Start from Position":
                            # Start from the specified position
                            if start_position >= len(all_images):
                                st.error(f"Start position {start_position} is out of range. Album has {len(all_images)} images.")
                                st.session_state.indexing_running = False
                                images_to_process = []
                            else:
                                images_to_process = all_images[start_position:]
                                status_message = f"Indexing {len(images_to_process)} images (starting from position {start_position})..."
                        else:  # Reset
                            images_to_process = all_images
                            status_message = f"Indexing all {len(images_to_process)} images from the beginning..."
                        
                        if not images_to_process:
                            if resume_method == "Auto (Use Saved Progress)":
                                st.success("All images in this album have already been indexed!")
                            st.session_state.indexing_running = False
                        else:
                            status_text.text(status_message)
                            
                            # Create a ThreadPoolExecutor for parallel processing
                            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                                # Submit tasks for each image
                                future_to_image = {}
                                
                                for image_key in images_to_process:
                                    if not st.session_state.indexing_running:
                                        break
                                        
                                    try:
                                        # Get image from S3
                                        image_bytes = get_image_from_s3(s3_bucket, image_key)
                                        
                                        # Submit indexing task
                                        future = executor.submit(
                                            asyncio.run,
                                            index_image(
                                                image_key=image_key,
                                                image_bytes=image_bytes,
                                                collection_id=collection_id,
                                                max_faces=max_faces
                                            )
                                        )
                                        
                                        future_to_image[future] = image_key
                                    except Exception as e:
                                        st.error(f"Error processing {os.path.basename(image_key)}: {e}")
                                        stats["failed_images"] += 1
                                
                                # Process completed tasks
                                for i, future in enumerate(concurrent.futures.as_completed(future_to_image)):
                                    if not st.session_state.indexing_running:
                                        break
                                        
                                    image_key = future_to_image[future]
                                    try:
                                        faces_detected, faces_indexed = future.result()
                                        
                                        stats["processed_images"] += 1
                                        stats["total_faces"] += faces_detected
                                        stats["indexed_faces"] += faces_indexed
                                        
                                        if faces_detected == 0:
                                            stats["skipped_images"] += 1
                                            
                                        # Add to indexed images set and save periodically
                                        indexed_images.add(image_key)
                                        if stats["processed_images"] % 10 == 0:  # Save every 10 images
                                            save_indexed_images(st.session_state.indexed_images_dict)
                                        
                                        # Update status
                                        current_position = start_position + stats["processed_images"] if resume_method == "Start from Position" else stats["processed_images"]
                                        status_text.text(f"Processed {stats['processed_images']}/{len(images_to_process)}: {os.path.basename(image_key)} (Position: {current_position}/{len(all_images)})")
                                        
                                        # Update stats display
                                        stats_text.text(
                                            f"Processed: {stats['processed_images']}/{len(images_to_process)} | "
                                            f"Faces indexed: {stats['indexed_faces']} | "
                                            f"Skipped: {stats['skipped_images']} | "
                                            f"Failed: {stats['failed_images']} | "
                                            f"Position: {current_position}/{len(all_images)}"
                                        )
                                        
                                        # Update progress - force a rerender by using progress_bar.progress()
                                        progress = float(stats['processed_images']) / float(len(images_to_process))
                                        # Ensure progress is between 0 and 1
                                        progress = max(0.0, min(1.0, progress))
                                        progress_bar.progress(progress)
                                        
                                        # Add a small sleep to allow UI to update
                                        time.sleep(0.01)
                                        
                                    except Exception as e:
                                        st.error(f"Error processing {os.path.basename(image_key)}: {e}")
                                        stats["failed_images"] += 1
                            
                            # Save final progress
                            save_indexed_images(st.session_state.indexed_images_dict)
                            
                            # Calculate total time
                            total_time = time.time() - start_time
                            
                            # Reset indexing state
                            st.session_state.indexing_running = False
                            
                            # Display final results
                            if stats["processed_images"] > 0:
                                st.success("Indexing completed!")
                                
                                # Display stats
                                st.subheader("Indexing Statistics")
                                st.write(f"Album: {selected_album}")
                                st.write(f"Collection: {collection_id}")
                                st.write(f"Total images in album: {len(all_images)}")
                                if resume_method == "Start from Position":
                                    st.write(f"Started from position: {start_position}")
                                    st.write(f"Ended at position: {start_position + stats['processed_images']}")
                                elif resume_method == "Auto (Use Saved Progress)":
                                    st.write(f"Already indexed: {stats['already_indexed']}")
                                st.write(f"Processed images: {stats['processed_images']}")
                                st.write(f"Skipped images (no faces): {stats['skipped_images']}")
                                st.write(f"Failed images: {stats['failed_images']}")
                                st.write(f"Total faces detected: {stats['total_faces']}")
                                st.write(f"Faces indexed: {stats['indexed_faces']}")
                                st.write(f"Total time: {total_time:.2f} seconds")
                                
                                if stats["processed_images"] > 0:
                                    st.write(f"Average time per image: {total_time / stats['processed_images']:.2f} seconds")
                                
                                if stats["indexed_faces"] > 0:
                                    st.write(f"Average time per face: {total_time / stats['indexed_faces']:.2f} seconds")
                                
                                # Show next position for resuming
                                next_position = start_position + stats["processed_images"] if resume_method == "Start from Position" else stats["processed_images"]
                                if next_position < len(all_images):
                                    st.info(f"To continue indexing, use position {next_position} as your starting point.")
                            else:
                                st.warning("No images were processed.")


if __name__ == "__main__":
    main() 