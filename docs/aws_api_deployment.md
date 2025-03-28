# AWS Deployment Documentation

## Overview
This document details the AWS infrastructure and configuration required to deploy the Face Recognition API service. The deployment uses AWS ECS Fargate for container orchestration, with an Application Load Balancer for traffic distribution.

## Infrastructure Components

### 1. ECR (Elastic Container Registry)
- **Repository Name**: `facerec-api`
- **Image Tag**: `latest`
- **Platform**: `linux/amd64`
- **Build Command**:
  ```bash
  docker build --platform linux/amd64 -t facerec-api:latest -f docker/api/Dockerfile .
  docker tag facerec-api:latest ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/facerec-api:latest
  docker push ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/facerec-api:latest
  ```

### 2. ECS (Elastic Container Service)
#### Cluster
- **Name**: `facerec-api-cluster`
- **Launch Type**: FARGATE
- **Capacity Providers**: FARGATE, FARGATE_SPOT

#### Task Definition
- **Family**: `facerec-api`
- **CPU**: 1024 (1 vCPU)
- **Memory**: 4096 MB
- **Container Definition**:
  ```json
  {
    "name": "api",
    "image": "${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/facerec-api:latest",
    "portMappings": [
      {
        "containerPort": 8000,
        "protocol": "tcp"
      }
    ],
    "environment": [
      {
        "name": "ENVIRONMENT",
        "value": "production"
      }
    ],
    "secrets": [
      {
        "name": "AWS_ACCESS_KEY_ID",
        "valueFrom": "/facerec/AWS_ACCESS_KEY_ID"
      },
      {
        "name": "AWS_SECRET_ACCESS_KEY",
        "valueFrom": "/facerec/AWS_SECRET_ACCESS_KEY"
      },
      {
        "name": "PINECONE_API_KEY",
        "valueFrom": "/facerec/PINECONE_API_KEY"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/facerec-api",
        "awslogs-region": "${AWS_REGION}",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }
  ```

#### Service
- **Name**: `facerec-api`
- **Desired Count**: 1
- **Launch Type**: FARGATE
- **Auto Scaling Configuration**:
  - Scale up when CPU > 70%
  - Scale down when CPU < 30%
  - Minimum tasks: 1
  - Maximum tasks: 2

### 3. Application Load Balancer
- **Name**: `facerec-api-alb`
- **Scheme**: internet-facing
- **Type**: application
- **Listener**:
  - Port: 80
  - Protocol: HTTP
  - Default Action: Forward to target group
- **Target Group**:
  - Name: `facerec-api-tg`
  - Protocol: HTTP
  - Port: 8000
  - Target Type: ip
  - Health Check Path: `/health`
  - Health Check Port: 8000
  - Health Check Protocol: HTTP
  - Healthy Threshold: 2
  - Unhealthy Threshold: 2
  - Timeout: 5 seconds
  - Interval: 30 seconds

### 4. IAM Roles and Policies

#### Task Execution Role
- **Name**: `ecsTaskExecutionRole`
- **Policies**:
  - `service-role/AmazonECSTaskExecutionRolePolicy`
  - Custom policy for SSM Parameter Store access:
    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "ssm:GetParameters",
            "ssm:GetParameter"
          ],
          "Resource": [
            "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT}:parameter/facerec/*"
          ]
        }
      ]
    }
    ```

#### Task Role
- **Name**: `ecsTaskRole`
- **Policies**:
  - Custom policy for AWS services access:
    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject"
          ],
          "Resource": [
            "arn:aws:s3:::${BUCKET_NAME}/*"
          ]
        }
      ]
    }
    ```

### 5. Security Groups

#### ALB Security Group
- **Name**: `facerec-api-alb-sg`
- **Inbound Rules**:
  - HTTP (80) from 0.0.0.0/0
- **Outbound Rules**:
  - All traffic to ECS Tasks Security Group

#### ECS Tasks Security Group
- **Name**: `facerec-api-ecs-sg`
- **Inbound Rules**:
  - HTTP (8000) from ALB Security Group
- **Outbound Rules**:
  - All traffic to 0.0.0.0/0

### 6. SSM Parameter Store
Parameters stored in AWS Systems Manager Parameter Store:
- `/facerec/AWS_ACCESS_KEY_ID` (SecureString)
- `/facerec/AWS_SECRET_ACCESS_KEY` (SecureString)
- `/facerec/PINECONE_API_KEY` (SecureString)

### 7. CloudWatch
- **Log Group**: `/ecs/facerec-api`
- **Retention**: 30 days
- **Metrics**:
  - CPU Utilization
  - Memory Utilization
  - Request Count
  - Target Response Time

## Deployment Process

1. Build and push Docker image:
   ```bash
   docker build --platform linux/amd64 -t facerec-api:latest -f docker/api/Dockerfile .
   docker tag facerec-api:latest ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/facerec-api:latest
   docker push ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/facerec-api:latest
   ```

2. Create/Update SSM Parameters:
   ```bash
   aws ssm put-parameter --name "/facerec/AWS_ACCESS_KEY_ID" --type SecureString --value "YOUR_ACCESS_KEY"
   aws ssm put-parameter --name "/facerec/AWS_SECRET_ACCESS_KEY" --type SecureString --value "YOUR_SECRET_KEY"
   aws ssm put-parameter --name "/facerec/PINECONE_API_KEY" --type SecureString --value "YOUR_PINECONE_KEY"
   ```

3. Register Task Definition:
   ```bash
   aws ecs register-task-definition --cli-input-json file://task-definition.json
   ```

4. Update Service:
   ```bash
   aws ecs update-service --cluster facerec-api-cluster --service facerec-api --force-new-deployment
   ```

## Monitoring and Maintenance

### Health Checks
- Application health endpoint: `/health`
- ALB health check path: `/health`
- Health check interval: 30 seconds
- Healthy threshold: 2
- Unhealthy threshold: 2
- Timeout: 5 seconds

### Logging
- Container logs are sent to CloudWatch Logs
- Log group: `/ecs/facerec-api`
- Log retention: 30 days

### Metrics
Key metrics to monitor:
- CPU Utilization
- Memory Utilization
- Request Count
- Target Response Time
- Error Rates

## Cost Estimation
Monthly costs (approximate):
- ECS Fargate: ~$20-30 (1 task running continuously)
- ALB: ~$20
- ECR: Negligible
- CloudWatch: Negligible
- Total: ~$40-50/month

## Security Considerations
1. All sensitive data stored in SSM Parameter Store
2. VPC with private subnets for ECS tasks
3. Security groups limiting access
4. IAM roles with minimal required permissions
5. HTTPS recommended for production (not currently configured)

## Future Improvements
1. Add HTTPS support with ACM certificate
2. Implement WAF for additional security
3. Set up CloudWatch Alarms
4. Configure backup strategy
5. Implement blue-green deployments
6. Add Route 53 DNS configuration
7. Set up CI/CD pipeline 