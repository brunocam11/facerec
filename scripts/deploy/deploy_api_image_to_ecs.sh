#!/bin/bash

#==============================================================================
# deploy_api_image_to_ecs.sh
#==============================================================================
#
# This script handles the deployment of the FaceRec API Docker image to AWS ECS.
# It is designed for regular code deployments and assumes the infrastructure
# (ECS cluster, service, task definition) is already set up via Terraform.
#
# Usage:
#   ./deploy_api_image_to_ecs.sh
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Docker installed and running
#   - .env.prod.api file with required environment variables
#   - Existing ECS cluster and service (managed by Terraform)
#
# What this script does:
#   1. Builds the Docker image for linux/amd64
#   2. Pushes the image to ECR
#   3. Gets the latest task definition
#   4. Updates the ECS service to use the new image
#
# Note: This script is for code deployments only. For infrastructure changes
#       (environment variables, CPU/memory, etc.), use Terraform instead.
#
#==============================================================================

# Exit on error
set -e

# Load environment variables
source .env.prod.api

# Configuration
AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPOSITORY_NAME="facerec-api"
ECS_CLUSTER_NAME="facerec-cluster"
ECS_SERVICE_NAME="facerec-api"

echo "🚀 Deploying API service to AWS..."

# Build Docker image for linux/amd64
echo "📦 Building Docker image..."
docker build --platform linux/amd64 -t ${ECR_REPOSITORY_NAME}:latest -f docker/api/Dockerfile .

# Log in to ECR
echo "🔑 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Tag and push image
echo "⬆️ Pushing image to ECR..."
docker tag ${ECR_REPOSITORY_NAME}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}:latest

# Get the latest task definition
echo "📝 Getting latest task definition..."
TASK_DEFINITION_ARN=$(aws ecs describe-task-definition \
    --task-definition facerec-worker-task-staging \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

# Update service with the latest task definition
echo "🔄 Updating ECS service..."
aws ecs update-service \
    --cluster ${ECS_CLUSTER_NAME} \
    --service ${ECS_SERVICE_NAME} \
    --task-definition ${TASK_DEFINITION_ARN} \
    --force-new-deployment

echo "✅ Deployment initiated!"
echo "📊 Monitor deployment: https://${AWS_REGION}.console.aws.amazon.com/ecs/home?region=${AWS_REGION}#/clusters/${ECS_CLUSTER_NAME}/services/${ECS_SERVICE_NAME}/events" 