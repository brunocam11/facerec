#!/bin/bash
set -e

# Only build the image if it doesn't exist or if --rebuild flag is passed
if [[ "$1" == "--rebuild" ]] || ! docker image inspect facerec-worker-dev >/dev/null 2>&1; then
    echo "Building development Docker image with hot reload..."
    docker build -t facerec-worker-dev -f Dockerfile.worker.dev .
else
    echo "Using existing Docker image. Use --rebuild to force rebuild."
fi

# Kill any existing container
docker rm -f facerec-worker-dev 2>/dev/null || true

echo "Running worker in development mode with hot reload..."
echo "Changes to Python files will automatically restart the worker"
docker run -it --name facerec-worker-dev \
  --rm \
  --env-file .env.docker \
  -p 8265:8265 \
  -v "$(pwd)/app:/app/app" \
  --shm-size=4g \
  facerec-worker-dev

# Final metrics
echo "Creating metrics summary files..."
mkdir -p ./metrics
docker logs facerec-worker-dev > ./metrics/worker_logs.txt
grep "Successfully processed" ./metrics/worker_logs.txt > ./metrics/successful_jobs.txt
grep "No faces detected" ./metrics/worker_logs.txt > ./metrics/no_faces_jobs.txt
grep "Error" ./metrics/worker_logs.txt > ./metrics/error_jobs.txt

# Extract stats
echo "=== PROCESSING SUMMARY ===" > ./metrics/summary.txt
echo "Total jobs processed: $(grep "Successfully processed job" ./metrics/worker_logs.txt | wc -l)" >> ./metrics/summary.txt
echo "Images with faces: $(grep "found [1-9]" ./metrics/worker_logs.txt | wc -l)" >> ./metrics/summary.txt
echo "Images with no faces: $(grep "No faces detected" ./metrics/worker_logs.txt | wc -l)" >> ./metrics/summary.txt
echo "Errors: $(grep "Error in Ray actor" ./metrics/worker_logs.txt | wc -l)" >> ./metrics/summary.txt
echo "Average processing time: $(grep "Stats: Processed" ./metrics/worker_logs.txt | tail -1)" >> ./metrics/summary.txt
cat ./metrics/summary.txt

# To queue test messages in another terminal:
# poetry run python -m app.cli.image_queue_producer --total 5 --test-mode 