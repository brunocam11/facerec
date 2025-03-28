# Face Recognition Service

A distributed face recognition service with separate API and worker components.

## Project Structure

```
facerec/
├── docker/
│   ├── api/              # API service Docker configuration
│   └── worker/           # Worker service Docker configuration
├── scripts/
│   ├── deploy/          # Deployment scripts
│   └── dev/             # Development scripts
└── app/                 # Application code
```

## Quick Start

1. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

2. Start services locally:
   ```bash
   # Start API
   ./scripts/dev/start-api.sh
   
   # Start Worker (in another terminal)
   ./scripts/dev/start-worker.sh
   ```

3. Deploy to AWS:
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

## Architecture

### API Service
- FastAPI-based REST API
- Handles face matching requests
- Deployed on ECS Fargate
- Scales based on HTTP request load

### Worker Service
- Processes face indexing tasks from SQS
- Uses Ray for distributed processing
- Deployed on EC2 spot instances
- Scales based on SQS queue depth

## Development

1. Make changes to the code
2. Test locally using development scripts
3. Deploy to AWS using deployment scripts

## Troubleshooting

1. **Worker not processing messages**
   - Check SQS queue depth
   - Verify worker logs

2. **API performance issues**
   - Check CloudWatch metrics
   - Verify model cache

3. **Deployment failures**
   - Check AWS credentials
   - Verify ECR repository exists
   - Check task definition

## License

MIT License - See LICENSE file 