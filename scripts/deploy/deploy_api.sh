#!/bin/bash

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

# Create ECR repository if it doesn't exist
aws ecr describe-repositories --repository-names ${ECR_REPOSITORY_NAME} || \
    aws ecr create-repository --repository-name ${ECR_REPOSITORY_NAME}

# Tag and push image
echo "⬆️ Pushing image to ECR..."
docker tag ${ECR_REPOSITORY_NAME}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}:latest

# Update task definition
echo "📝 Updating task definition..."
TASK_DEFINITION_FILE="docker/api/task-definition.json"

# Replace placeholders in task definition
sed -i.bak "s/\${AWS_ACCOUNT_ID}/${AWS_ACCOUNT_ID}/g" ${TASK_DEFINITION_FILE}
sed -i.bak "s/\${AWS_REGION}/${AWS_REGION}/g" ${TASK_DEFINITION_FILE}
sed -i.bak "s/\${ECR_REPOSITORY_URI}/${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com\/${ECR_REPOSITORY_NAME}/g" ${TASK_DEFINITION_FILE}

# Register new task definition
TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
    --cli-input-json file://${TASK_DEFINITION_FILE} \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

# Update service
echo "🔄 Updating ECS service..."
aws ecs update-service \
    --cluster ${ECS_CLUSTER_NAME} \
    --service ${ECS_SERVICE_NAME} \
    --task-definition ${TASK_DEFINITION_ARN} \
    --force-new-deployment

echo "✅ Deployment initiated!"
echo "📊 Monitor deployment: https://${AWS_REGION}.console.aws.amazon.com/ecs/home?region=${AWS_REGION}#/clusters/${ECS_CLUSTER_NAME}/services/${ECS_SERVICE_NAME}/events" 