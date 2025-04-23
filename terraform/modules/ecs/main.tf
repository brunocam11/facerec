# Data source for current region
data "aws_region" "current" {}

# ECS Cluster
resource "aws_ecs_cluster" "facerec_worker" {
  name = "${var.project_name}-worker-cluster-${var.environment}"
  
  tags = {
    Name        = "${var.project_name}-worker-cluster-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "facerec_worker" {
  name              = "/ecs/${var.project_name}-${var.ecs_container_name}-${var.environment}"
  retention_in_days = 14
  
  tags = {
    Name        = "/ecs/${var.project_name}-${var.ecs_container_name}-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "facerec_worker" {
  family                   = "${var.ecs_task_family}-${var.environment}"
  requires_compatibilities = ["EC2"]
  network_mode            = "bridge"
  cpu                     = var.task_cpu
  memory                  = var.task_memory
  execution_role_arn      = var.ecs_task_execution_role_arn
  task_role_arn           = var.ecs_task_role_arn
  
  container_definitions = jsonencode([
    {
      name  = var.ecs_container_name
      image = "${var.ecr_repository_url}:latest"
      
      cpu       = var.task_cpu
      memory    = var.task_memory
      essential = true
      
      linuxParameters = {
        sharedMemorySize = floor(var.task_memory * 0.3)  # 30% of task memory for shared memory
      }
      
      environment = [
        {
          name  = "RAY_MEMORY_PER_PROCESS"
          value = var.ray_memory_per_process
        },
        {
          name  = "AWS_REGION"
          value = data.aws_region.current.name
        },
        {
          name  = "PINECONE_INDEX_NAME"
          value = var.pinecone_index_name
        },
        {
          name  = "MIN_FACE_CONFIDENCE"
          value = var.min_face_confidence
        },
        {
          name  = "PINECONE_API_KEY"
          value = var.pinecone_api_key
        },
        {
          name  = "SQS_BATCH_SIZE"
          value = var.sqs_batch_size
        },
        {
          name  = "S3_BUCKET_REGION"
          value = data.aws_region.current.name
        },
        {
          name  = "AWS_S3_BUCKET"
          value = var.s3_bucket_name
        },
        {
          name  = "MAX_FACES_PER_IMAGE"
          value = "10"
        },
        {
          name  = "SIMILARITY_THRESHOLD"
          value = "0.8"
        },
        {
          name  = "CONTAINER_MEMORY_THRESHOLD"
          value = "0.85"
        },
        {
          name  = "SQS_QUEUE_NAME"
          value = var.sqs_queue_name
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.facerec_worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
  
  tags = {
    Name        = "${var.ecs_task_family}-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# ECS Service
resource "aws_ecs_service" "facerec_worker" {
  name            = "${var.project_name}-${var.ecs_service_name}-service-${var.environment}"
  cluster         = aws_ecs_cluster.facerec_worker.id
  task_definition = aws_ecs_task_definition.facerec_worker.arn
  launch_type     = "EC2"
  scheduling_strategy = "DAEMON"

  tags = {
    Name        = "${var.project_name}-${var.ecs_service_name}-service-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# SQS Queue Length Alarm for Scale Up
resource "aws_cloudwatch_metric_alarm" "sqs_queue_length" {
  alarm_name          = "${var.project_name}-sqs-queue-length-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2  # Require 2 evaluation periods
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60  # Check every minute
  statistic           = "Average"
  threshold           = 100  # Increased threshold
  alarm_description   = "This alarm monitors the SQS queue visible messages for scaling decisions"
  alarm_actions       = [aws_autoscaling_policy.scale_up.arn]
  
  dimensions = {
    QueueName = var.sqs_queue_name
  }
  
  treat_missing_data = "notBreaching"
  datapoints_to_alarm = 2  # Require 2 datapoints
  
  tags = {
    Name        = "${var.project_name}-sqs-queue-length-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# ASG Scaling Policies
resource "aws_autoscaling_policy" "scale_up" {
  name                   = "${var.project_name}-scale-up-${var.environment}"
  autoscaling_group_name = var.autoscaling_group_name
  policy_type            = "StepScaling"
  adjustment_type        = "ChangeInCapacity"
  metric_aggregation_type = "Average"
  estimated_instance_warmup = 180  # 3-minute warmup
  
  step_adjustment {
    scaling_adjustment          = 1
    metric_interval_lower_bound = 0
    metric_interval_upper_bound = 500
  }
  
  step_adjustment {
    scaling_adjustment          = 1
    metric_interval_lower_bound = 500
    metric_interval_upper_bound = 1000
  }
  
  step_adjustment {
    scaling_adjustment          = 1
    metric_interval_lower_bound = 1000
  }
}

resource "aws_autoscaling_policy" "scale_down" {
  name                   = "${var.project_name}-scale-down-${var.environment}"
  autoscaling_group_name = var.autoscaling_group_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = -1
  cooldown              = 300  # Increased cooldown for scale down
}

# Scale Down Alarm
resource "aws_cloudwatch_metric_alarm" "scale_down" {
  alarm_name          = "${var.project_name}-scale-down-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2  # Require 2 evaluation periods
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 120  # Check every 2 minutes
  statistic           = "Average"
  threshold           = 25  # Scale down when queue has less than 25 messages
  alarm_description   = "This alarm triggers scale down when queue has fewer messages"
  alarm_actions       = [aws_autoscaling_policy.scale_down.arn]
  
  dimensions = {
    QueueName = var.sqs_queue_name
  }
  
  treat_missing_data = "notBreaching"
  datapoints_to_alarm = 2
  
  tags = {
    Name        = "${var.project_name}-scale-down-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
} 