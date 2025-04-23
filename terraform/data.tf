# Data source to fetch the latest Amazon ECS-optimized AMI
data "aws_ssm_parameter" "ecs_optimized_ami" {
  name = "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id"
}

# Data source to get information about the ECR repository
data "aws_ecr_repository" "facerec_worker" {
  name = var.ecr_repository_name
}

# Data source to get the AWS account ID
data "aws_caller_identity" "current" {}

# Data source to get the AWS region
data "aws_region" "current" {}

# Data source to get default VPC if not specified
data "aws_vpc" "default" {
  default = true
  count   = var.vpc_id == "" ? 1 : 0
}

# Data source to get default subnets if not specified
data "aws_subnets" "private" {
  count = length(var.private_subnet_ids) == 0 ? 1 : 0
  filter {
    name   = "vpc-id"
    values = [var.vpc_id == "" ? data.aws_vpc.default[0].id : var.vpc_id]
  }
}

data "aws_security_group" "default" {
  count  = length(var.security_group_ids) == 0 ? 1 : 0
  name   = "default"
  vpc_id = var.vpc_id == "" ? data.aws_vpc.default[0].id : var.vpc_id
}

# Local variables derived from data sources
locals {
  # Get default VPC if not specified
  vpc_id = var.vpc_id != "" ? var.vpc_id : data.aws_vpc.default[0].id

  # Get default subnets if not specified
  private_subnet_ids = length(var.private_subnet_ids) > 0 ? var.private_subnet_ids : data.aws_subnets.private[0].ids

  # Get default security groups if not specified
  security_group_ids = length(var.security_group_ids) > 0 ? var.security_group_ids : [data.aws_security_group.default[0].id]

  # Get SQS queue ARN - directly use the variable
  sqs_queue_arn = var.sqs_queue_arn
  
  # ECS task and cluster full names
  cluster_name = "${var.project_name}-${var.ecs_cluster_name}-${var.environment}"
  service_name = "${var.project_name}-${var.ecs_service_name}-${var.environment}"
  task_family  = "${var.project_name}-${var.ecs_task_family}-${var.environment}"
  
  # Resource ARN prefix
  aws_account_id = data.aws_caller_identity.current.account_id
  aws_region     = data.aws_region.current.name
} 