# Terraform Implementation Plan for ECS Auto-Scaling

## Project Structure

```
terraform/
├── main.tf         # Main module configuration
├── variables.tf    # Input variables
├── outputs.tf      # Output values
├── locals.tf       # Local variables
├── providers.tf    # AWS provider configuration
├── modules/
│   ├── ecs/        # ECS-specific resources
│   ├── asg/        # Auto Scaling Group configuration
│   ├── sqs/        # SQS queue configuration
│   └── iam/        # IAM roles and policies
└── terraform.tfvars # Variable values (gitignored)
```

## Key Resources to Create

1. **AWS Provider Configuration**
   - Region: us-east-1 (or your preferred region)
   - Profile: default (or your AWS profile)

2. **VPC and Networking** (assuming existing, otherwise would need to be created)
   - Reference to existing VPC
   - Reference to existing private subnets
   - Reference to existing security groups

3. **IAM Module**
   - ECS Task Execution Role
   - ECS Task Role (with SQS permissions)
   - EC2 Instance Profile for ECS
   - Spot Instance Interruption Handling Policy

4. **SQS Module**
   - SQS Queue (if not existing)
   - Dead Letter Queue
   - Queue Policy

5. **ASG Module with Spot Instances**
   - Launch Template with Spot Request
   - Auto Scaling Group
   - IAM Instance Profile
   - Spot Fleet Request (if needed)
   - Spot Instance Interruption Handler (Lambda)

6. **ECS Module**
   - ECS Cluster
   - ECS Task Definition
   - ECS Service with One-Task-Per-Instance
   - Capacity Provider
   - Service Auto Scaling Target
   - Service Auto Scaling Policy

## Important Terraform Resources

```hcl
# ECS Cluster
resource "aws_ecs_cluster" "facerec_worker" {
  name = "facerec-worker-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# Launch Template for Spot Instances
resource "aws_launch_template" "ecs_spot_instance" {
  name_prefix   = "facerec-worker-spot-"
  image_id      = data.aws_ami.ecs_optimized.id
  instance_type = "c5.2xlarge"  # 8 vCPU, 16GB RAM
  
  iam_instance_profile {
    name = aws_iam_instance_profile.ecs_instance.name
  }
  
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 30
      volume_type = "gp3"
      delete_on_termination = true
    }
  }
  
  network_interfaces {
    associate_public_ip_address = false
    security_groups             = var.security_group_ids
  }
  
  instance_market_options {
    market_type = "spot"
    spot_options {
      spot_instance_type = "one-time"
      instance_interruption_behavior = "terminate"
    }
  }
  
  user_data = base64encode(<<-EOF
    #!/bin/bash
    echo ECS_CLUSTER=${aws_ecs_cluster.facerec_worker.name} >> /etc/ecs/ecs.config
    echo ECS_ENABLE_SPOT_INSTANCE_DRAINING=true >> /etc/ecs/ecs.config
    echo ECS_ENABLE_CONTAINER_METADATA=true >> /etc/ecs/ecs.config
    # Increase Docker default shm size
    echo 'OPTIONS="--default-shm-size=2g"' >> /etc/sysconfig/docker
  EOF
  )
  
  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "facerec-worker-ecs-instance"
    }
  }
}

# Capacity Provider
resource "aws_ecs_capacity_provider" "asg_capacity_provider" {
  name = "facerec-worker-capacity-provider"
  
  auto_scaling_group_provider {
    auto_scaling_group_arn = aws_autoscaling_group.facerec_worker.arn
    
    managed_scaling {
      status                    = "ENABLED"
      target_capacity           = 100
      minimum_scaling_step_size = 1
      maximum_scaling_step_size = 5
      instance_warmup_period    = 300
    }
    
    managed_termination_protection = "DISABLED"
  }
}

# Cluster Capacity Provider Association
resource "aws_ecs_cluster_capacity_providers" "facerec_worker" {
  cluster_name = aws_ecs_cluster.facerec_worker.name
  
  capacity_providers = [
    aws_ecs_capacity_provider.asg_capacity_provider.name
  ]
  
  default_capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.asg_capacity_provider.name
    weight            = 1
    base              = 0
  }
}

# Auto Scaling Group with Spot Instances
resource "aws_autoscaling_group" "facerec_worker" {
  name                 = "facerec-worker-asg"
  min_size             = 0
  max_size             = 5
  desired_capacity     = 0
  vpc_zone_identifier  = var.private_subnet_ids
  health_check_type    = "EC2"
  health_check_grace_period = 300
  
  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 0
      on_demand_percentage_above_base_capacity = 0  # Use 100% spot instances
      spot_allocation_strategy                 = "capacity-optimized"  # Optimizes for availability
    }
    
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.ecs_spot_instance.id
        version            = "$Latest"
      }
      
      # Optional - specify multiple instance types for better spot availability
      override {
        instance_type = "c5.2xlarge"  # Primary instance type
      }
      override {
        instance_type = "m5.2xlarge"  # Fallback instance type with same CPU/similar RAM
      }
    }
  }
  
  tag {
    key                 = "AmazonECSManaged"
    value               = true
    propagate_at_launch = true
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "facerec_worker" {
  family                   = "facerec-worker-task"
  requires_compatibilities = ["EC2"]
  network_mode             = "bridge"
  cpu                      = 2048
  memory                   = 13312
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  
  container_definitions = jsonencode([
    {
      name      = "facerec-worker"
      image     = "${data.aws_ecr_repository.facerec_worker.repository_url}:latest"
      essential = true
      
      environment = [
        { name = "FACE_RECOGNITION_MEMORY_THRESHOLD", value = "0.8" },
        { name = "RAY_memory_per_process", value = "1073741824" },
        { name = "SQS_BATCH_SIZE", value = "3" }
      ]
      
      mountPoints = []
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/facerec-worker"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      linuxParameters = {
        sharedMemorySize = 2048  # 2GB shared memory
      }
    }
  ])
}

# ECS Service with One-Task-Per-Instance
resource "aws_ecs_service" "facerec_worker" {
  name                              = "facerec-worker-service"
  cluster                           = aws_ecs_cluster.facerec_worker.id
  task_definition                   = aws_ecs_task_definition.facerec_worker.arn
  desired_count                     = 0  # Will scale with auto-scaling
  scheduling_strategy               = "REPLICA"
  health_check_grace_period_seconds = 60
  
  capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.asg_capacity_provider.name
    weight            = 1
    base              = 0
  }
  
  placement_constraints {
    type = "distinctInstance"  # Ensures 1 task per instance
  }
  
  placement_strategy {
    type  = "spread"
    field = "attribute:ecs.availability-zone"
  }
  
  deployment_controller {
    type = "ECS"
  }
  
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  
  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 0
}

# Application Auto Scaling for ECS Service
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 5  # Match max ASG size for 1:1 task:instance ratio
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.facerec_worker.name}/${aws_ecs_service.facerec_worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Target Tracking Scaling Policy based on SQS Queue
resource "aws_appautoscaling_policy" "sqs_policy" {
  name               = "facerec-worker-sqs-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace
  
  target_tracking_scaling_policy_configuration {
    target_value = 1.0  # 1 message per task
    
    predefined_metric_specification {
      predefined_metric_type = "SQSQueueMessagesVisiblePerTask"
      resource_label         = "${var.sqs_queue_arn}/${aws_ecs_service.facerec_worker.name}"
    }
    
    scale_in_cooldown  = 300  # 5 minutes
    scale_out_cooldown = 30   # 30 seconds
  }
}

## IAM and Roles Management

Terraform will create all necessary IAM roles and policies as part of the deployment. This includes:

1. **ECS Task Execution Role** - Created by:
   ```hcl
   resource "aws_iam_role" "ecs_task_execution_role" {
     name = "facerec-worker-task-execution-role"
     assume_role_policy = jsonencode({
       Version = "2012-10-17",
       Statement = [{
         Action = "sts:AssumeRole",
         Effect = "Allow",
         Principal = {
           Service = "ecs-tasks.amazonaws.com"
         }
       }]
     })
   }

   resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
     role       = aws_iam_role.ecs_task_execution_role.name
     policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
   }
   ```

2. **ECS Task Role** (for SQS access) - Created by:
   ```hcl
   resource "aws_iam_role" "ecs_task_role" {
     name = "facerec-worker-task-role"
     assume_role_policy = jsonencode({
       Version = "2012-10-17",
       Statement = [{
         Action = "sts:AssumeRole",
         Effect = "Allow",
         Principal = {
           Service = "ecs-tasks.amazonaws.com"
         }
       }]
     })
   }

   resource "aws_iam_policy" "sqs_access_policy" {
     name        = "facerec-worker-sqs-access-policy"
     description = "Policy for facerec worker to access SQS"
     policy = jsonencode({
       Version = "2012-10-17",
       Statement = [{
         Effect   = "Allow",
         Action   = [
           "sqs:ReceiveMessage",
           "sqs:DeleteMessage",
           "sqs:GetQueueAttributes",
           "sqs:ChangeMessageVisibility"
         ],
         Resource = var.sqs_queue_arn
       }]
     })
   }

   resource "aws_iam_role_policy_attachment" "ecs_task_role_sqs_policy" {
     role       = aws_iam_role.ecs_task_role.name
     policy_arn = aws_iam_policy.sqs_access_policy.arn
   }
   ```

3. **EC2 Instance Profile for ECS** - Created by:
   ```hcl
   resource "aws_iam_role" "ecs_instance_role" {
     name = "facerec-worker-ecs-instance-role"
     assume_role_policy = jsonencode({
       Version = "2012-10-17",
       Statement = [{
         Action = "sts:AssumeRole",
         Effect = "Allow",
         Principal = {
           Service = "ec2.amazonaws.com"
         }
       }]
     })
   }

   resource "aws_iam_role_policy_attachment" "ecs_instance_role_policy" {
     role       = aws_iam_role.ecs_instance_role.name
     policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
   }

   resource "aws_iam_instance_profile" "ecs_instance" {
     name = "facerec-worker-ecs-instance-profile"
     role = aws_iam_role.ecs_instance_role.name
   }
   ```

## CloudWatch Alarms Management

Terraform will create CloudWatch alarms for monitoring the system:

1. **Target Tracking Alarms** - Created automatically by the scaling policies
2. **Additional Service Monitoring Alarms** - Created explicitly:
   ```hcl
   resource "aws_cloudwatch_metric_alarm" "ecs_service_high_cpu" {
     alarm_name          = "facerec-worker-service-high-cpu"
     comparison_operator = "GreaterThanThreshold"
     evaluation_periods  = 2
     metric_name         = "CPUUtilization"
     namespace           = "AWS/ECS"
     period              = 60
     statistic           = "Average"
     threshold           = 80
     alarm_description   = "This alarm monitors ECS Service CPU utilization"
     
     dimensions = {
       ClusterName = aws_ecs_cluster.facerec_worker.name
       ServiceName = aws_ecs_service.facerec_worker.name
     }
   }
   ```

## Getting the Latest ECR Image

To ensure we always use the latest image from ECR, we'll use a data source to fetch the repository URL:

```hcl
data "aws_ecr_repository" "facerec_worker" {
  name = "facerec-worker"  # Use your actual repository name
}
```

Then reference it in the task definition with `:latest` tag as shown in the task definition above. This ensures that when tasks are launched, they'll pull the most recent image with the "latest" tag from your ECR repository.

## Implementation Steps

1. **Initialize Terraform**
   ```
   terraform init
   ```

2. **Create Terraform Variables File**
   - Create `terraform.tfvars` with your specific values
   - Include AWS region, subnet IDs, VPC ID, etc.

3. **Plan the Deployment**
   ```
   terraform plan -out=plan.out
   ```

4. **Apply the Configuration**
   ```
   terraform apply plan.out
   ```

5. **Verify Resources**
   - Check AWS Console to verify all resources
   - Test auto-scaling by sending messages to SQS queue

## Notes and Considerations

- Use Terraform state locking to prevent concurrent modifications
- Consider using remote state storage (S3 + DynamoDB)
- Include proper tagging strategy for all resources
- Use data sources to reference existing resources
- Include appropriate timeouts for resource creation
- Test the scaling behavior with controlled load tests

## Spot Instance Considerations

- Spot instances can be interrupted with 2-minute notice
- ECS automatically drains tasks from instances that receive interruption notice
- Consider implementing a Lambda function to handle spot interruption events
- Be prepared for potential capacity issues during high-demand periods
- Monitor spot instance interruptions and consider fallback strategies

## IAM and Security

- Follow principle of least privilege for all IAM roles
- Use secure strings for sensitive variables
- Consider KMS encryption for sensitive data
- Ensure proper security group rules for EC2 instances
- Include necessary permissions for Spot instance requests 