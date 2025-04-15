# Face Recognition Service Scripts

This directory contains scripts for development and deployment of the Face Recognition service.

## Directory Structure

```
scripts/
├── dev/           # Development scripts
│   ├── run_dev_api.sh     # Run API locally
│   ├── run_dev_worker.sh  # Run worker locally
│   └── monitor_worker.sh  # Monitor worker performance
└── deploy/        # Deployment scripts
    ├── deploy_api.sh      # Deploy API to AWS
    └── deploy_worker.sh   # Deploy worker to AWS
```

## Development Scripts

### `dev/run_dev_api.sh`
Builds and runs the API service locally for development.
```bash
./scripts/dev/run_dev_api.sh
```
- Builds Docker image
- Mounts model cache directory
- Exposes port 8000
- Shows container logs

### `dev/run_dev_worker.sh`
Builds and runs the worker service locally for development.
```bash
./scripts/dev/run_dev_worker.sh
```
- Builds Docker image
- Mounts model cache directory
- Configures Ray for local processing
- Shows container logs

### `dev/monitor_worker.sh`
Monitors the worker service performance and resource usage.
```bash
./scripts/dev/monitor_worker.sh
```
- Tracks CPU and memory usage
- Monitors Ray cluster status
- Logs performance metrics
- Generates performance reports

## Deployment Scripts

### `deploy/deploy_api.sh`
Deploys the API service to AWS ECS Fargate.
```bash
./scripts/deploy/deploy_api.sh [environment]
```
- Builds Docker image
- Pushes to Amazon ECR
- Updates ECS service
- Supports different environments (default: production)

### `deploy/deploy_worker.sh`
Deploys the worker service to AWS ECS with spot instances.
```bash
./scripts/deploy/deploy_worker.sh [environment]
```
- Builds Docker image
- Pushes to Amazon ECR
- Updates ECS service
- Uses spot instances for cost optimization
- Supports different environments (default: production)

## Requirements

- Docker installed
- AWS CLI installed and configured
- AWS credentials with appropriate permissions
- Python 3.11
- Poetry for dependency management

## Environment Variables

Required environment variables:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`
- `ENVIRONMENT` (development/production) 