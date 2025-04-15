# Docker Image Build and Deployment Process

This document outlines the process for building, pushing, and deploying the FaceRec worker Docker image to AWS ECS.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed and running
- Access to the AWS ECR repository
- Access to the AWS ECS cluster

## Build Process

### 1. Building the Docker Image

```bash
# Navigate to the project root
cd /path/to/facerec

# Build the Docker image
./prod_worker.sh --rebuild
```

This will build the Docker image using the Dockerfile in the project root.

### 2. Tagging and Pushing to ECR

```bash
# Tag the image for ECR
docker tag facerec-worker-prod:latest 431835747280.dkr.ecr.us-east-1.amazonaws.com/facerec-worker:latest

# Log in to ECR (if not already authenticated)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 431835747280.dkr.ecr.us-east-1.amazonaws.com

# Push the image to ECR
docker push 431835747280.dkr.ecr.us-east-1.amazonaws.com/facerec-worker:latest
```

## Deployment Process

### 1. Updating the ECS Task Definition

Use the AWS Console to create a new revision of the task definition:

1. Log into the AWS Management Console
2. Navigate to Elastic Container Service (ECS)
3. Select "Task Definitions" from the left navigation
4. Find the `facerec-worker-task` task definition and click on it
5. Click "Create new revision"
6. Make any necessary changes:
   - Ensure image is set to: `431835747280.dkr.ecr.us-east-1.amazonaws.com/facerec-worker:latest`
   - For EC2 Spot instances optimization:
     - Set container CPU to "0" (unlimited)
     - Remove explicit memory limit or set to "0"
     - Set memory reservation to 512MB minimum
7. Click "Create" to register the new task definition

### 2. Updating the ECS Service

1. Navigate to the ECS Cluster:
   - Select "Clusters" from the left navigation
   - Select the `facerec-worker-cluster` or appropriate cluster
2. Select the service to update
3. Click "Update"
4. Select the latest task definition revision
5. Review other settings and click "Update Service"

## Resource Configuration

### Understanding the Resource Hierarchy

1. **Inside Container (Ray Configuration)**:
   - Configured in `app/consumers/indexing_consumer/main.py`
   - Controls how Ray uses resources within the container
   - Dynamically calculates CPU and memory usage

2. **ECS Task Definition**:
   - Sets resource limits for the container itself
   - When optimizing for spot instances, set container CPU to "0" and remove memory limits

3. **EC2 Spot Instances (ASG)**:
   - Physical resources on each host machine
   - Managed through Auto Scaling Group

### Common Dependency Issues

#### Pydantic Version Mismatch

If you see the error `ModuleNotFoundError: No module named 'pydantic._internal'`, this indicates a mismatch between your code and the installed pydantic version:

- **Error Analysis**: Your code is trying to use pydantic v2.x features, but pydantic v1.x is installed
- **Solution**: Update the pydantic version in your Dockerfile or requirements.txt:
  ```
  # In Dockerfile
  RUN pip install pydantic==2.5.2 pydantic-settings==2.1.0
  
  # Or in requirements.txt
  pydantic==2.5.2
  pydantic-settings==2.1.0
  ```

#### Fixing in Production

If this error happens in a deployed container:

1. Update your `requirements.txt` with the correct version
2. Rebuild the Docker image using `./dev_worker.sh --rebuild`
3. Tag and push the new image to ECR
4. Update the ECS task definition and service as described earlier

## Verifying Deployment

To verify that your deployment is using the correct image:

```bash
# Check the latest task definition
aws ecs describe-task-definition --task-definition facerec-worker-task:latest | grep -A 5 image

# List running tasks
aws ecs list-tasks --cluster spotted-cluster

# Describe a specific task to verify the image
aws ecs describe-tasks --cluster spotted-cluster --tasks <task-id> | grep image
```

## Troubleshooting

- **Image Pull Failures**: Verify ECR permissions and that the image exists
- **Task Failures**: Check CloudWatch logs for container errors
- **Resource Issues**: Ensure the EC2 instances have enough capacity for your containers
- **Module Not Found Errors**: Check that your dependencies in requirements.txt match the versions your code expects
- **Container Crashes**: Examine CloudWatch logs for the specific error messages

## Notes on Optimizations

The worker application includes several optimizations:

1. **Model Caching**: Global cache to avoid reinitializing the face model
2. **Limited CPU Usage**: Ray configured to use available CPUs efficiently
3. **Memory Management**: Explicit garbage collection and increased memory threshold
4. **Performance Tracking**: Detailed timing statistics and enhanced logging

These optimizations help ensure faster processing times and better resource utilization. 