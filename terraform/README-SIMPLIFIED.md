# Quick Start Guide for Face Recognition Worker Terraform

This guide provides a simplified approach to deploy the face recognition worker infrastructure.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform v1.0.0 or newer installed

## Quick Setup

1. **Initialize the configuration**:
   ```
   cd terraform
   make setup    # Create terraform.tfvars from example
   make init     # Initialize Terraform
   ```

2. **Edit terraform.tfvars**:
   - Set your Pinecone API key
   - Set S3 bucket names
   - If not using default VPC, set your VPC IDs, subnet IDs, and security groups

3. **Deploy**:
   ```
   make plan     # Create a plan
   make apply    # Apply the plan
   ```

## Auto-detected Resources

With the simplified configuration, you only need to specify custom resources:

- **Default VPC**: If you don't specify a VPC ID, the default VPC will be used
- **Default Subnets**: If you don't specify subnet IDs, subnets from the default VPC will be used
- **Default Security Group**: If you don't specify security groups, the default security group will be used

## Common Commands

```
make help       # Show available commands
make validate   # Validate the configuration
make destroy    # Destroy all resources when you're done
```

## Key Resources Created

- ECS Cluster with Spot Instances (c5.2xlarge)
- Auto Scaling Group with capacity for up to 5 instances
- ECS Service with one-task-per-instance constraint
- Auto Scaling based on SQS queue depth
- CloudWatch Alarms for monitoring

## Important Note

The configuration uses IAM roles for authentication within AWS and securely stores the Pinecone API key in AWS Secrets Manager. 