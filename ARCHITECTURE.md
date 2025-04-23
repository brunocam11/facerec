# Architectural Overview

This document provides a detailed explanation of the architecture behind this face recognition service, including infrastructure choices, system components, and the rationale behind key design decisions.

## System Architecture

This face recognition service uses a distributed architecture with separate components for API serving and background processing.

### Core Components

1. **API Service** - A FastAPI application that:
   - Handles synchronous face matching requests (real-time face verification)
   - Enqueues face indexing operations for asynchronous processing
   - Exposes a RESTful API for client applications

2. **Worker Service** - A distributed processing system that:
   - Consumes messages from SQS queue
   - Processes face recognition tasks in parallel using Ray
   - Indexes face embeddings in the vector database
   - Scales based on queue depth

3. **Persistence Layer** - Comprised of:
   - S3 for image storage
   - Pinecone for vector database (face embeddings)
   - SQS for message queue

## Key Design Decisions

### 1. Why Use Ray for Inter-Process Communication and Model Sharing

[Ray](https://www.ray.io/) is used primarily as an Inter-Process Communication (IPC) mechanism to maintain a single, shared face recognition model in memory that can be accessed by multiple processes. This design choice provides several key benefits:

- **Memory Efficiency**: Instead of each process loading its own copy of the face recognition model (which can be large), Ray enables a single model instance to be shared across processes
- **Resource Optimization**: Significantly reduces memory usage since the model parameters (several hundred MB) are loaded only once
- **Improved Throughput**: Eliminates the model loading/initialization time for each individual task
- **Consistent Inference**: Ensures all processes use exactly the same model parameters for inference

Ray's architecture allows us to effectively scale processing while maintaining memory efficiency, which is critical for production deployments where model size can be a significant constraint. The `initialize_ray()` function in `app/consumers/indexing_consumer/main.py` calculates the optimal number of worker processes based on available system memory, ensuring we can maximize throughput without triggering out-of-memory errors.

Ray was chosen over alternatives like multiprocessing, multithreading, or other task queue systems because:
- It provides a clean object-sharing mechanism across processes
- It handles serialization/deserialization of complex Python objects
- It offers a straightforward API for distributed computing
- It automatically manages the object lifetime and garbage collection

### 2. Dependency Injection Pattern

We implement a clean dependency injection pattern through `app/core/container.py` to:

- Ensure services are initialized in the correct order
- Provide a single source of truth for service instances
- Enable easier testing and mocking of dependencies
- Allow for flexible service reconfiguration

### 3. Face Recognition Pipeline

Our face recognition pipeline consists of the following stages:

1. **Image Acquisition**: Retrieves images from S3
2. **Face Detection**: Identifies face regions within images
3. **Feature Extraction**: Generates embeddings for each detected face
4. **Vector Storage**: Stores embeddings in Pinecone for efficient similarity search
5. **Face Matching**: Compares face embeddings to find matches

The pipeline is implemented using InsightFace, an advanced open-source face analysis toolkit that provides state-of-the-art accuracy.

### 4. Infrastructure as Code

All infrastructure is defined using Terraform to ensure:

- Consistent deployments
- Version-controlled infrastructure
- Reproducible environments
- Easy scaling and management

## Containerization Strategy

The application uses a multi-stage Docker build approach:

1. **API Container** (`docker/api/Dockerfile`):
   - Slim Python base image
   - Poetry for dependency management
   - Proper health checks
   - Non-root user for security

2. **Worker Container** (`docker/worker/Dockerfile.worker.prod`):
   - Optimized for batch processing
   - Configured with appropriate system libraries
   - Structured for maximum throughput
   - Resource-aware configuration

## Scaling Model

The service scales horizontally based on workload:

- **API Service**: Scales based on HTTP request load using ECS service auto-scaling
- **Worker Service**: Scales based on SQS queue depth using EC2 Auto Scaling Groups
- **Cost Optimization**: Worker uses EC2 Spot Instances for cost savings (up to 90% vs on-demand)

## Security Considerations

The architecture implements several security best practices:

- IAM roles for service-to-service authentication
- S3 bucket access control
- Secrets management for API keys
- Network isolation through security groups
- Data encryption in transit and at rest