# Face Recognition CLI Tools

This directory contains command-line tools for interacting with the face recognition system. These tools help you index faces, test face detection, and perform bulk operations.

## Available Tools

### Image Queue Producer (`image_queue_producer.py`) 

Bulk enqueue face indexing jobs to SQS for distributed processing. This tool scans an S3 bucket for images and sends them to the SQS queue for asynchronous processing by worker nodes.

```bash
# Process images from a specific album
poetry run python -m app.cli.image_queue_producer --album-id vacation-photos --max-images 500

# Process images from all albums
poetry run python -m app.cli.image_queue_producer --max-images 1000
```

Arguments:
- `--album-id`: Specific album ID to process (optional)
- `--max-images`: Maximum number of images to queue (optional, but required when processing all albums)

The script will:
1. Connect to S3 and identify images matching the criteria
2. Create SQS messages with the proper format for worker processing
3. Send the messages to the queue configured in your environment settings
4. Track progress and provide statistics about the operation

### S3 Album Indexer (`index_s3_album.py`)

Directly index faces from S3 images into Pinecone without using the queue. Good for smaller albums or when you need immediate processing.

```bash
poetry run python -m app.cli.index_s3_album \
  --bucket your-photos-bucket \
  --album wedding-2023 \
  --collection wedding-faces \
  --prefix albums \
  --max-faces 10 \
  --min-confidence 0.9
```

Arguments:
- `--bucket`: S3 bucket name (required)
- `--album`: Album ID/directory in S3 (required)
- `--collection`: Collection ID to index into (required)
- `--prefix`: S3 prefix to prepend to album ID (optional)
- `--max-faces`: Maximum number of faces to detect per image (default: 5)
- `--min-confidence`: Minimum confidence threshold for face detection (default: 0.9)

The script will:
1. List all images in the specified album
2. Process each image to detect faces
3. Index faces that meet the confidence threshold into Pinecone
4. Display detailed statistics about the indexing process

### Face Detection Tool (`detect_faces.py`)

Test face detection on local images and visualize the results. Helpful for debugging or verifying detection quality.

```bash
poetry run python -m app.cli.detect_faces path/to/your/image.jpg --no-save
```

Arguments:
- `image_path`: Path to the local image file (required)
- `--no-save`: Option to prevent saving the annotated image (optional)

The script will:
1. Load the specified image
2. Detect faces using the InsightFace recognition service
3. Display the image with bounding boxes showing detected faces
4. Save the annotated image (unless `--no-save` is specified)
5. Output detailed information about each detected face

## Environment Setup

These CLI tools require proper environment configuration. Make sure you have a `.env` file at the project root with the following settings:

```env
# AWS Credentials
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# S3 Configuration
AWS_S3_BUCKET=your-default-bucket
AWS_S3_BUCKET_REGION=us-east-1

# Pinecone Configuration
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=your-pinecone-index

# SQS Configuration
SQS_QUEUE_NAME=face-indexing-queue
SQS_BATCH_SIZE=10

# Face Recognition Settings
MAX_FACES_PER_IMAGE=10
MIN_FACE_CONFIDENCE=0.9
```

## Common Workflows

### Processing a Complete Album Directly

For smaller albums that you want to process immediately:

```bash
# Index an entire wedding album
poetry run python -m app.cli.index_s3_album \
  --bucket photos-bucket \
  --album wedding-2023 \
  --collection wedding \
  --max-faces 10
```

### Distributed Processing for Large Albums

For very large albums that need distributed processing:

```bash
# Queue all images from the album for processing
poetry run python -m app.cli.image_queue_producer --album-id large-album --max-images 5000

# The worker services will process these images asynchronously
```

### Testing Face Detection

When you need to verify face detection is working correctly:

```bash
# Download an image from S3 to test locally
aws s3 cp s3://your-bucket/path/to/image.jpg ./test-image.jpg

# Run face detection
poetry run python -m app.cli.detect_faces test-image.jpg
```

## Troubleshooting

### Common Issues

1. **AWS Authentication Errors**: 
   - Ensure your AWS credentials are set in the .env file
   - Verify AWS CLI is configured correctly: `aws configure`
   - Check IAM permissions for S3 and SQS access

2. **S3 Access Problems**:
   - Verify the bucket exists: `aws s3 ls s3://your-bucket`
   - Check bucket permissions
   - Ensure album paths are correct (check for leading/trailing slashes)

3. **SQS Issues**:
   - Verify queue exists: `aws sqs get-queue-url --queue-name your-queue`
   - Check queue permissions
   - Ensure SQS_QUEUE_NAME in your .env matches the actual queue

4. **Pinecone Connection Problems**:
   - Verify PINECONE_API_KEY is correct
   - Check if the index exists in Pinecone console
   - Ensure your IP is allowed in Pinecone network policies

5. **Memory Issues with Large Images**:
   - For large images, try processing fewer at a time
   - Adjust `--max-faces` to a lower value