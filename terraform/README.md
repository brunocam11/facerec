# Face Recognition Worker Terraform Configuration

This Terraform project sets up the AWS infrastructure for a face recognition worker system on Amazon ECS with auto-scaling based on SQS queue depth.

## Architecture

The configuration creates the following resources:

- ECS Cluster with Container Insights enabled
- ECS Task Definition with 13GB memory allocation
- ECS Service with one-task-per-instance constraint
- Auto Scaling Group with Spot Instances (c5.2xlarge)
- Capacity Provider with managed scaling
- Application Auto Scaling based on SQS queue depth
- IAM roles and policies for ECS tasks and instances
- CloudWatch Logs and Alarms

## Prerequisites

- Terraform v1.0.0 or newer
- AWS CLI configured with appropriate credentials
- Existing VPC with private subnets
- Existing security groups
- Existing ECR repository with Docker image

## Getting Started

1. Copy `terraform.tfvars.example` to `terraform.tfvars` and update with your values:

```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars` with your actual AWS resource IDs and settings.

3. Initialize Terraform:

```bash
terraform init
```

4. Plan the deployment:

```bash
terraform plan -out=plan.out
```

5. Apply the configuration:

```bash
terraform apply plan.out
```

## Configuration Options

### Using Existing SQS Queue

By default, the configuration uses an existing SQS queue. Set `create_sqs_queue = true` in `terraform.tfvars` to create a new queue.

### Spot Instance Configuration

The configuration uses Spot Instances with c5.2xlarge (8 vCPU, 16GB RAM) as the primary instance type and m5.2xlarge as a fallback type. These can be adjusted in `terraform.tfvars`.

### Auto Scaling Settings

- Minimum capacity: 0 (scales to zero when idle)
- Maximum capacity: 5 (can run up to 5 tasks on 5 instances)
- Target value: 1 message per task
- Scale-out cooldown: 30 seconds
- Scale-in cooldown: 300 seconds (5 minutes)

## Monitoring

The deployment includes CloudWatch alarms for:

- ECS Service CPU Utilization (>80%)
- ECS Service Memory Utilization (>80%)

## Clean Up

To destroy all resources created by this configuration:

```bash
terraform destroy
```

## Notes

- The configuration uses the `bridge` network mode for compatibility.
- Shared memory is increased to 2GB to prevent OOM errors.
- Managed draining is enabled for graceful task termination. 