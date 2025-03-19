# VPC Endpoints for SSM
# resource "aws_vpc_endpoint" "ssm" {
#   vpc_id            = var.vpc_id
#   service_name      = "com.amazonaws.${data.aws_region.current.name}.ssm"
#   vpc_endpoint_type = "Interface"
#   subnet_ids        = var.subnet_ids
#   security_group_ids = var.security_group_ids
#   private_dns_enabled = true

#   tags = {
#     Name        = "${var.project_name}-ssm-endpoint-${var.environment}"
#     Environment = var.environment
#     Project     = var.project_name
#   }
# }

# resource "aws_vpc_endpoint" "ec2messages" {
#   vpc_id            = var.vpc_id
#   service_name      = "com.amazonaws.${data.aws_region.current.name}.ec2messages"
#   vpc_endpoint_type = "Interface"
#   subnet_ids        = var.subnet_ids
#   security_group_ids = var.security_group_ids
#   private_dns_enabled = true

#   tags = {
#     Name        = "${var.project_name}-ec2messages-endpoint-${var.environment}"
#     Environment = var.environment
#     Project     = var.project_name
#   }
# }

# resource "aws_vpc_endpoint" "ssmmessages" {
#   vpc_id            = var.vpc_id
#   service_name      = "com.amazonaws.${data.aws_region.current.name}.ssmmessages"
#   vpc_endpoint_type = "Interface"
#   subnet_ids        = var.subnet_ids
#   security_group_ids = var.security_group_ids
#   private_dns_enabled = true

#   tags = {
#     Name        = "${var.project_name}-ssmmessages-endpoint-${var.environment}"
#     Environment = var.environment
#     Project     = var.project_name
#   }
# }

# resource "aws_vpc_endpoint" "logs" {
#   vpc_id            = var.vpc_id
#   service_name      = "com.amazonaws.${data.aws_region.current.name}.logs"
#   vpc_endpoint_type = "Interface"
#   subnet_ids        = var.subnet_ids
#   security_group_ids = var.security_group_ids
#   private_dns_enabled = true

#   tags = {
#     Name        = "${var.project_name}-logs-endpoint-${var.environment}"
#     Environment = var.environment
#     Project     = var.project_name
#   }
# }

# Data source for current region
data "aws_region" "current" {}

# Launch Template
resource "aws_launch_template" "ecs_launch_template" {
  name_prefix   = "${var.project_name}-lt-${var.environment}-"
  image_id      = var.ami_id
  instance_type = var.instance_type
  
  network_interfaces {
    associate_public_ip_address = true
    security_groups            = var.security_group_ids
  }
  
  iam_instance_profile {
    name = var.instance_profile_name
  }
  
  user_data = base64encode(<<-END
    #!/bin/bash
    # Configure ECS cluster
    echo "ECS_CLUSTER=${var.cluster_name}" > /etc/ecs/ecs.config
    echo "ECS_ENABLE_CONTAINER_METADATA=true" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_SPOT_INSTANCE_DRAINING=true" >> /etc/ecs/ecs.config
    echo "ECS_CONTAINER_STOP_TIMEOUT=120" >> /etc/ecs/ecs.config
    echo "ECS_LOGLEVEL=debug" >> /etc/ecs/ecs.config
    
    # Configure Docker shared memory size
    mkdir -p /etc/docker
    echo '{"default-shm-size": "2g"}' > /etc/docker/daemon.json
    
    # Restart Docker to apply shared memory configuration
    systemctl restart docker
    
    # Log for debugging
    echo "ECS agent started for cluster: ${var.cluster_name}" >> /var/log/ecs-startup.log
    date >> /var/log/ecs-startup.log
    systemctl status ecs >> /var/log/ecs-startup.log
  END
  )
  
  tag_specifications {
    resource_type = "instance"
    tags = {
      Name        = "${var.project_name}-ecs-instance-${var.environment}"
      Environment = var.environment
      Project     = var.project_name
      AmazonECSManaged = "true"
    }
  }
  
  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

# Auto Scaling Group
resource "aws_autoscaling_group" "facerec_asg" {
  name                = "${var.project_name}-asg-${var.environment}"
  vpc_zone_identifier = var.subnet_ids
  desired_capacity    = var.asg_desired_capacity
  max_size           = var.max_asg_size
  min_size           = var.asg_min_size
  target_group_arns  = []  # We don't need target groups for this use case
  
  health_check_grace_period = var.health_check_grace_period
  health_check_type        = "EC2"
  
  mixed_instances_policy {
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.ecs_launch_template.id
        version           = "$Latest"
      }
      
      override {
        instance_type = "c5.2xlarge"
      }
    }
    
    instances_distribution {
      on_demand_base_capacity                  = 0
      on_demand_percentage_above_base_capacity = 0
      spot_allocation_strategy                 = "capacity-optimized"
    }
  }
  
  tag {
    key                 = "AmazonECSManaged"
    value              = "true"
    propagate_at_launch = true
  }
  
  tag {
    key                 = "Name"
    value              = "${var.project_name}-ecs-instance-${var.environment}"
    propagate_at_launch = true
  }
  
  tag {
    key                 = "Environment"
    value              = var.environment
    propagate_at_launch = true
  }
  
  tag {
    key                 = "Project"
    value              = var.project_name
    propagate_at_launch = true
  }
  
  tag {
    key                 = "ManagedBy"
    value              = "Terraform"
    propagate_at_launch = true
  }
  
  wait_for_capacity_timeout = "10m"
} 