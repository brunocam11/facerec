# SQS Module - Create or use existing SQS queue
module "sqs" {
  source = "./modules/sqs"
  
  project_name  = var.project_name
  environment   = var.environment
  
  create_sqs_queue             = var.create_sqs_queue
  sqs_queue_name               = var.sqs_queue_name
  visibility_timeout_seconds   = var.sqs_visibility_timeout
  message_retention_seconds    = var.sqs_message_retention_seconds
  create_dlq                   = true
  max_receive_count            = 5
}

# IAM Module - Create necessary roles and policies
module "iam" {
  source = "./modules/iam"
  
  project_name  = var.project_name
  environment   = var.environment
  
  # Use SQS queue ARN directly
  sqs_queue_arn = var.sqs_queue_arn
  
  # Add S3 bucket name
  s3_bucket_name = var.s3_bucket_name
  
  ecs_task_execution_role_name = "ecs-task-execution-role"
  ecs_task_role_name           = "ecs-task-role"
  ecs_instance_role_name       = "ecs-instance-role"
}

# ASG Module - Create Auto Scaling Group with Spot Instances
module "asg" {
  source = "./modules/asg"
  
  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  
  vpc_id             = local.vpc_id
  private_subnet_ids = local.private_subnet_ids
  security_group_ids = local.security_group_ids
  subnet_ids         = local.private_subnet_ids
  
  cluster_name         = module.ecs.ecs_cluster_name
  instance_profile_name = module.iam.ecs_instance_profile_name
  
  instance_type = var.instance_type
  ami_id        = data.aws_ssm_parameter.ecs_optimized_ami.value
  
  asg_min_size         = var.asg_min_size
  max_asg_size         = var.max_asg_size
  asg_desired_capacity = var.asg_desired_capacity
  
  health_check_grace_period = var.health_check_grace_period
  instance_warmup_period    = var.instance_warmup_period
  
  ebs_volume_size           = var.ebs_volume_size
  ebs_volume_type          = var.ebs_volume_type
  ebs_delete_on_termination = var.ebs_delete_on_termination
}

# ECS Module - Create ECS Cluster, Task Definition, Service and Auto Scaling
module "ecs" {
  source = "./modules/ecs"
  
  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  
  ecr_repository_url = var.ecr_repository_url
  ecs_container_name = var.ecs_container_name
  ecs_task_family    = var.ecs_task_family
  ecs_service_name   = var.ecs_service_name
  
  ecs_task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  ecs_task_role_arn          = module.iam.ecs_task_role_arn
  
  task_cpu    = var.task_cpu
  task_memory = var.task_memory
  
  s3_bucket_name   = var.s3_bucket_name
  s3_bucket_region = var.s3_bucket_region
  
  pinecone_index_name  = var.pinecone_index_name
  pinecone_api_key     = var.pinecone_api_key
  
  max_faces_per_image     = var.max_faces_per_image
  min_face_confidence     = var.min_face_confidence
  similarity_threshold    = var.similarity_threshold
  container_memory_threshold = var.container_memory_threshold
  ray_memory_per_process  = var.ray_memory_per_process
  sqs_batch_size         = var.sqs_batch_size
  
  sqs_queue_arn = var.sqs_queue_arn
  sqs_queue_name = var.sqs_queue_name
  
  autoscaling_group_name = module.asg.asg_name
}