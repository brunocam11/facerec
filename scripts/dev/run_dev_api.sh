#!/bin/bash

# Exit on error
set -e

# Check if environment file exists
if [ ! -f .env.docker.api ]; then
    echo "Error: .env.docker.api file not found!"
    exit 1
fi

# Stop and remove existing container if it exists
if [ "$(docker ps -aq -f name=facerec-api)" ]; then
    echo "Stopping existing API container..."
    docker stop facerec-api
    docker rm facerec-api
fi

# Build the image
echo "Building API image..."
docker build -t facerec-api:latest -f docker/api/Dockerfile .

# Create model cache directory if it doesn't exist
mkdir -p model_cache

# Run the container
echo "Starting API container..."
docker run -d \
  --name facerec-api \
  -p 8000:8000 \
  -v "$(pwd)/model_cache:/app/model_cache" \
  --env-file .env.docker.api \
  facerec-api:latest

# Show logs
echo "Container logs:"
docker logs -f facerec-api 