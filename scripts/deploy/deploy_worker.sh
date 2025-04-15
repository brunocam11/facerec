#!/bin/bash
set -e

# Only build the image if it doesn't exist or if --rebuild flag is passed
if [[ "$1" == "--rebuild" ]] || ! docker image inspect facerec-worker-prod-local >/dev/null 2>&1; then
    echo "Building production Docker image for x86_64 architecture..."
    docker build --platform linux/amd64 -t facerec-worker-prod-local -f Dockerfile.worker.prod .
else
    echo "Using existing Docker image. Use --rebuild to force rebuild."
fi

# Kill any existing container
docker rm -f facerec-worker-prod-local 2>/dev/null || true

echo "Running production worker locally for testing..."
# Using a different port to avoid conflicts with dev container
docker run -it --name facerec-worker-prod-local \
  --platform linux/amd64 \
  --rm \
  --env-file .env.docker \
  -p 8266:8265 \
  --shm-size=4g \
  facerec-worker-prod-local

# Final metrics
echo "Creating metrics summary files..."
mkdir -p ./metrics/prod
docker logs facerec-worker-prod-local > ./metrics/prod/worker_logs.txt
grep "Successfully processed" ./metrics/prod/worker_logs.txt > ./metrics/prod/successful_jobs.txt || true
grep "No faces detected" ./metrics/prod/worker_logs.txt > ./metrics/prod/no_faces_jobs.txt || true
grep "Error" ./metrics/prod/worker_logs.txt > ./metrics/prod/error_jobs.txt || true

# Extract stats
echo "=== PRODUCTION WORKER PROCESSING SUMMARY ===" > ./metrics/prod/summary.txt
echo "Total jobs processed: $(grep "Successfully processed job" ./metrics/prod/worker_logs.txt | wc -l)" >> ./metrics/prod/summary.txt || true
echo "Images with faces: $(grep "found [1-9]" ./metrics/prod/worker_logs.txt | wc -l)" >> ./metrics/prod/summary.txt || true
echo "Images with no faces: $(grep "No faces detected" ./metrics/prod/worker_logs.txt | wc -l)" >> ./metrics/prod/summary.txt || true
echo "Errors: $(grep "Error in Ray actor" ./metrics/prod/worker_logs.txt | wc -l)" >> ./metrics/prod/summary.txt || true
echo "Average processing time: $(grep "Stats: Processed" ./metrics/prod/worker_logs.txt | tail -1)" >> ./metrics/prod/summary.txt || true

cat ./metrics/prod/summary.txt

# To queue test messages in another terminal:
# poetry run python -m app.cli.image_queue_producer --total 5 --test-mode

# Deployment commands:
# 1. Tag the image for ECR:
#    docker tag facerec-worker-prod-local:latest 431835747280.dkr.ecr.us-east-1.amazonaws.com/facerec-worker:latest
#
# 2. Log in to ECR:
#    aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 431835747280.dkr.ecr.us-east-1.amazonaws.com
#
# 3. Push the image to ECR:
#    docker push 431835747280.dkr.ecr.us-east-1.amazonaws.com/facerec-worker:latest 