# Face Recognition Service
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready, distributed face recognition service built on AWS, with separate API and worker components. This service is optimized for AWS infrastructure but designed with extensibility in mind.

## Cloud Provider Support

This service is currently optimized for AWS infrastructure. While the core face recognition logic is cloud-agnostic, the infrastructure and deployment are AWS-specific. We welcome contributions to support other cloud providers!

### Why AWS?
- Scalable infrastructure with ECS and EC2
- Cost-effective with spot instances
- Robust security features through IAM
- Seamless integration with S3 and SQS
- Production-ready deployment patterns

### Why Use This Service?

*   **Cost-Effective:** Designed as a potential alternative to more expensive managed services like AWS Rekognition, especially for high-volume processing, leveraging spot instances and optimized components.
*   **Control & Extensibility:** Provides more control over the underlying models and infrastructure compared to managed services. The modular design allows for easier customization and extension.
*   **Cloud Agnostic Core (Potential):** While currently deployed on AWS, the core application logic aims for cloud neutrality, welcoming contributions for other platforms.

## Project Structure

```
facerec/
├── docker/
│   ├── api/              # API service Docker configuration
│   └── worker/           # Worker service Docker configuration
├── scripts/
│   ├── deploy/          # AWS deployment scripts
│   └── dev/             # Development scripts
├── app/
│   ├── api/             # API endpoints and models
│   ├── cli/             # Command-line tools
│   ├── consumers/       # SQS message consumers
│   ├── core/            # Core application components
│   ├── domain/          # Domain models and interfaces
│   ├── infrastructure/  # Infrastructure integrations
│   └── services/        # Business logic services
└── terraform/           # Infrastructure as code
```

## Quick Start

1. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your AWS settings
   # IMPORTANT: Ensure your .env file is NOT committed to version control. It's already in .gitignore.
   ```

2. Install dependencies using Poetry:
   ```bash
   poetry install
   ```

3. Start services locally (choose ONE method):

   **Method A: Using Development Scripts (Recommended)**
   ```bash
   # Start API
   ./scripts/dev/run_dev_api.sh 
   
   # Start Worker (in another terminal)
   ./scripts/dev/run_dev_worker.sh
   ```

   **Method B: Running Manually (Without Scripts/Docker)**
   ```bash
   # 1. Start the API server (using Poetry environment)
   #    poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

   # 2. Start the Indexing Worker (using Poetry environment, requires Ray)
   #    poetry run python -m app.consumers.indexing_consumer.main
   ```

4. Deploy to AWS:
   ```bash
   # Deploy API
   ./scripts/deploy/deploy-api.sh
   ```

## Environment Variables

Required variables in `.env`:
```env
# Environment
ENVIRONMENT=development

# Face Recognition Settings
MAX_FACES_PER_IMAGE=10
MIN_FACE_CONFIDENCE=0.9
SIMILARITY_THRESHOLD=0.8

# CORS Settings
ALLOWED_ORIGINS=http://localhost:3000

# Pinecone Settings
PINECONE_API_KEY=your_key
PINECONE_INDEX_NAME=your_index

# AWS Settings
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
AWS_S3_BUCKET=your_bucket
AWS_S3_BUCKET_REGION=us-east-1

# SQS Settings
SQS_QUEUE_NAME=your_queue
SQS_BATCH_SIZE=10
```

## API Usage Examples

Once the API service is running (e.g., locally on `http://localhost:8000`), you can interact with it. Here are examples using `curl`:

### Index Faces

Sends a request to index faces found in an image stored in your S3 bucket.

```bash
curl -X POST "http://localhost:8000/api/v1/face-recognition/index" \
     -H "Content-Type: application/json" \
     -d '{
           "bucket": "your-s3-bucket-name",
           "key": "path/to/your/image.jpg",
           "collection_id": "your_collection_id",
           "max_faces": 5
         }'
```

### Match Faces

Sends a request to find faces in a collection that are similar to faces in a query image (also stored in S3).

```bash
curl -X POST "http://localhost:8000/api/v1/face-recognition/match" \
     -H "Content-Type: application/json" \
     -d '{
           "bucket": "your-s3-bucket-name",
           "key": "path/to/query/image.jpg",
           "collection_id": "your_collection_id",
           "threshold": 0.8
         }'
```

*(Note: Replace placeholder values like `your-s3-bucket-name`, `path/to/your/image.jpg`, and `your_collection_id` with actual values.)*

## Architecture

### AWS Infrastructure
- **API Service**: Deployed on ECS Fargate
- **Worker Service**: Deployed on EC2 spot instances
- **Storage**: S3 for image storage
- **Queue**: SQS for task distribution
- **Vector Database**: Pinecone for face embeddings
- **Auto-scaling**: Based on SQS queue depth and API load

### Components
- **API Service**
  - FastAPI-based REST API
  - Handles face matching requests
  - Scales based on HTTP request load
  - Integrated with AWS services

- **Worker Service**
  - Processes face indexing tasks from SQS
  - Uses Ray for distributed processing
  - Optimized for EC2 spot instances
  - Scales based on SQS queue depth

## Development

This project uses [Poetry](https://python-poetry.org/) for dependency management.

1. Make changes to the code
2. Run linters/formatters (e.g., `poetry run black .`, `poetry run ruff .`, `poetry run mypy .`).
3. Run tests (see the `tests/` directory) using `poetry run pytest`.
4. Test locally using development scripts (`poetry run ./scripts/dev/...`).
5. Deploy to AWS using deployment scripts

## Troubleshooting

1. **Worker not processing messages**
   - Check SQS queue depth
   - Verify worker logs
   - Check EC2 instance status

2. **API performance issues**
   - Check CloudWatch metrics
   - Verify model cache
   - Monitor ECS task status

3. **Deployment failures**
   - Check AWS credentials
   - Verify ECR repository exists
   - Check task definition
   - Verify IAM roles and permissions

## Contributing

We welcome contributions! Please see the `CONTRIBUTING.md` file for guidelines. Some areas where contributions are particularly welcome:

- Support for other cloud providers
- Additional face recognition models
- Performance optimizations
- Documentation improvements

## Future Improvements

*   **Optional Indexing on Match:** Consider adding an option to the `/match` endpoint to optionally index the query face into a specified collection (potentially the same one being searched) after extracting its embedding.

## Important Considerations

*   **External Service Costs & Limits:** The overall cost-effectiveness and performance rely heavily on AWS services (S3, SQS, EC2 Spot Instances) and Pinecone. Users should carefully review the pricing models, free tier limitations, and potential costs associated with these external services based on their expected usage.
*   **Assumptions:** Performance benchmarks and cost savings compared to alternatives depend on specific workloads and configurations. Verify these assumptions for your use case.
*   **Security:** Ensure proper IAM roles, security groups, and credential management practices are followed, especially regarding AWS keys and Pinecone API keys stored in the environment.
