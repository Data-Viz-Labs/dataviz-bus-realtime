# Main Terraform configuration for Madrid Bus Real-Time Simulator
# This file orchestrates all infrastructure modules

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.33"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Timestream database and tables
module "timestream" {
  source = "./modules/timestream"

  database_name = var.timestream_database_name

  tags = var.tags
}

# IAM roles for Lambda and Fargate
module "iam" {
  source = "./modules/iam"

  timestream_database_arn = module.timestream.database_arn
  timestream_table_arns   = module.timestream.table_arns
  eventbridge_bus_arn     = module.eventbridge.event_bus_arn
  dynamodb_table_arn      = module.supporting.dynamodb_table_arn
  config_bucket_arn       = module.supporting.config_bucket_arn
  ecr_repository_arn      = module.fargate.ecr_repository_arn

  tags = var.tags
}

# API Gateway (REST and WebSocket)
module "api_gateway" {
  source = "./modules/api-gateway"

  lambda_execution_role_arn = module.iam.lambda_execution_role_arn

  timestream_database_name = module.timestream.database_name
  timestream_tables        = module.timestream.table_names
  dynamodb_table_name      = module.supporting.dynamodb_table_name

  participant_count = var.participant_count

  tags = var.tags
}

# Fargate services (ECS cluster and feeders)
module "fargate" {
  source = "./modules/fargate"

  vpc_id                    = module.supporting.vpc_id
  private_subnet_ids        = module.supporting.private_subnet_ids
  fargate_security_group_id = module.supporting.fargate_security_group_id

  timestream_database_name = module.timestream.database_name
  timestream_tables        = module.timestream.table_names
  eventbridge_bus_name     = module.eventbridge.event_bus_name
  config_bucket_name       = module.supporting.config_bucket_name

  ecs_task_role_arn      = module.iam.ecs_task_role_arn
  ecs_execution_role_arn = module.iam.ecs_execution_role_arn

  tags = var.tags
}

# EventBridge event bus and rules
module "eventbridge" {
  source = "./modules/eventbridge"

  lambda_websocket_arn = module.api_gateway.lambda_websocket_arn

  tags = var.tags
}

# Supporting resources (VPC, S3, DynamoDB, CloudWatch)
module "supporting" {
  source = "./modules/supporting"

  create_vpc = var.create_vpc
  vpc_cidr   = var.vpc_cidr

  tags = var.tags
}

# Amazon Location (route calculator and map)
module "location" {
  source = "./modules/location"

  tags = var.tags
}

# Cost Management (AWS Budgets and SNS notifications)
module "cost_management" {
  source = "./modules/cost-management"

  monthly_budget_limit = var.monthly_budget_limit
  budget_alert_emails  = var.budget_alert_emails

  tags = var.tags
}
