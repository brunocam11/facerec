# Face Recognition Service

A high-performance face recognition service that provides face detection, indexing, and search capabilities through a REST API. This project was created as a cost-effective alternative to AWS Rekognition, offering similar capabilities through a self-hosted solution at a fraction of the cost.

## Features

- Face detection and analysis
- Face indexing and search by collection
- High performance (~50ms per face)
- Production-ready accuracy (99.77% on LFW)
- Flexible integration options
- Self-hosted and cost-effective

## Quick Start

```bash
# Clone repository
git clone https://github.com/brunocam11/facerec.git
cd facerec

# Install dependencies
poetry install

# Set environment variables
cp .env.example .env
# Edit .env with your settings

# Run service
poetry run uvicorn app.main:app --reload
```

## Configuration

Key settings in `.env`:
```bash
# Core Settings
ENVIRONMENT=development
MAX_IMAGE_PIXELS=1920x1080

# Face Recognition
MAX_FACES_PER_IMAGE=20
MIN_FACE_CONFIDENCE=0.9
SIMILARITY_THRESHOLD=0.8

# Vector Store (Pinecone)
PINECONE_API_KEY=your_key
PINECONE_INDEX_NAME=face-recognition
```

## Integration

This service is designed to be flexible and easy to integrate:

- Organize faces into collections
- Reference source images by ID
- AWS Rekognition-compatible API
- Independent storage system

## Development

For database changes:
1. Update models in `app/infrastructure/database/models.py`
2. Generate migration: `alembic revision --autogenerate -m "Description"`
3. Apply migration: `alembic upgrade head`

## Running Tests

Run tests:
```bash
pytest
```

Run tests with detailed output:
```bash
pytest -s
```

The `-s` flag shows print statements and detailed output, which is useful for debugging. Running without `-s` gives a cleaner output focused on test results.

## License

MIT License - See LICENSE file 