terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "4.67.0"
    }
  }
  
  required_version = ">= 1.0.0"
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
} 