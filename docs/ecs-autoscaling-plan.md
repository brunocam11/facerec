# ECS Auto-Scaling System Architecture

This document outlines the complete architecture for the face recognition worker system with proper auto-scaling.

## Components Overview

1. **ECS Cluster**
   - Name: `facerec-worker-cluster`
   - Container Insights: Enabled

2. **ECS Task Definition**
   - Family: `facerec-worker-task`
   - CPU: 2048 (2 vCPU)
   - Memory: 13312 MiB (13GB)
   - Network Mode: `bridge`
   - Image: `facerec-worker:latest` (from existing ECR)
   - Essential: Yes
   - Shared Memory: 2GB
   - Environment Variables:
     - `FACE_RECOGNITION_MEMORY_THRESHOLD`: "0.8"
     - `RAY_memory_per_process`: "1073741824" (1GB)
     - `SQS_BATCH_SIZE`: "3" (reduced from 10 to prevent memory issues)

3. **ECS Capacity Provider**
   - Auto Scaling Group Provider
   - Managed Scaling: Enabled
   - Target Capacity: 100%
   - Minimum Scaling Step Size: 1
   - Maximum Scaling Step Size: 5
   - Instance Warmup Period: 300 seconds
   - Managed Termination Protection: Disabled
   - Managed Draining: Enabled

4. **Auto Scaling Group with Spot Instances**
   - Name: `facerec-worker-asg`
   - Min Size: 0
   - Max Size: 5
   - Desired Capacity: 0 (will scale based on demand)
   - Instance Type: c5.2xlarge (8 vCPU, 16GB RAM) - Spot Instances
   - Purchasing Option: Spot with On-Demand fallback
   - Spot Allocation Strategy: capacity-optimized (prioritizes availability)
   - AMI: Latest Amazon ECS-optimized AMI
   - Subnets: All private subnets across availability zones
   - Health Check Grace Period: 300 seconds
   - Health Check Type: EC2

5. **ECS Service**
   - Name: `facerec-worker-service`
   - Task Definition: `facerec-worker-task:latest`
   - Desired Count: 0 (will scale based on queue depth)
   - Launch Type: EC2
   - Capacity Provider Strategy:
     - Capacity Provider: ASG Capacity Provider
     - Weight: 1
     - Base: 0
   - Deployment Configuration:
     - Maximum Percent: 200
     - Minimum Healthy Percent: 0
     - Circuit Breaker: Enabled with rollback
   - Placement Strategy:
     - Type: spread
     - Field: attribute:ecs.availability-zone
   - Placement Constraints: 
     - Type: distinctInstance (ensures 1 task per instance)

6. **Service Auto Scaling**
   - Min Count: 0
   - Max Count: 5 (matching max instance count for 1:1 task:instance ratio)
   - Scale on: SQS Queue Depth
   - Target Value: 1 message per task
   - Scale-out Cooldown: 30 seconds
   - Scale-in Cooldown: 300 seconds (5 minutes)

7. **SQS Queue**
   - Name: `facerec-indexing-staging-queue`
   - Type: Standard
   - Visibility Timeout: 900 seconds (15 minutes)
   - Retention Period: 4 days
   - Message Size: 256 KB
   - Delivery Delay: None
   - Receive Message Wait Time: 0

## Detailed Configuration

### Task Sizing

The memory configuration is critical for this workload:
- Each face recognition worker uses ~530MB of memory
- The main process uses ~940MB
- Setting batch size to 3 ensures we don't exceed memory limits (~3.5GB for workers)
- Total container memory: 13GB within a 16GB instance
- `RAY_memory_per_process` set to 1GB to limit Ray worker memory usage
- Reserved ~3GB for system, Docker daemon, and OS overhead

### Instance to Task Mapping

- Each instance will run exactly one task (1:1 mapping)
- This is enforced through:
  1. The distinctInstance placement constraint
  2. Matching max ECS task count to max ASG size
  3. Target tracking scaling based on queue depth per task

### Auto-Scaling Chain

1. **Trigger**: SQS queue depth increases
2. **First Action**: ECS Service scales out (adds tasks)
3. **Second Action**: Capacity Provider notices task placement needs
4. **Third Action**: ASG scales out (adds EC2 instances, preferring Spot)
5. **Final Action**: New tasks are placed on new instances (1 per instance)

### Scale-In Behavior

1. Scale-in is conservative (5-minute cooldown)
2. When queue depth decreases below target, ECS service reduces desired count
3. As EC2 instances become underutilized, ASG will scale in
4. Managed draining ensures no tasks are terminated abruptly

## Health Monitoring

- ECS container health checks: None (relies on process exit codes)
- EC2 instance health: Default EC2 health checks
- Spot Instance interruption handling: 2-minute warning via metadata
- CloudWatch Alarms:
  - Target tracking alarms for ECS service (created automatically)
  - Target tracking alarms for ASG (created automatically)

## Environmental Considerations

- Docker shared memory increased to 2GB to prevent OOM errors
- Memory threshold set to 0.8 (80%) to prevent worker overload
- Small batch size (3) to prevent parallel processing memory spike
- Managed instance draining to gracefully complete tasks
- Spot instance interruption handler for graceful termination

## Deployment Strategy

- Implementation via Terraform
- All components in a single Terraform module
- Proper IAM roles and policies for ECS tasks and instance profiles
- CloudWatch logging for containers

## Metrics to Monitor

- SQS Queue depth
- ECS Service desired vs running tasks
- ASG instance count and utilization
- ECS task memory utilization
- Processing time per image
- Number of faces detected per image
- Spot instance interruption frequency 