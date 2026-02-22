# Variables for Fargate module

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "fargate_security_group_id" {
  description = "ID of the security group for Fargate services"
  type        = string
}

variable "timestream_database_name" {
  description = "Name of the Timestream database"
  type        = string
}

variable "timestream_tables" {
  description = "Map of Timestream table names"
  type = object({
    people_count = string
    sensor_data  = string
    bus_position = string
  })
}

variable "eventbridge_bus_name" {
  description = "Name of the EventBridge event bus"
  type        = string
}

variable "config_bucket_name" {
  description = "Name of the S3 bucket for configuration"
  type        = string
}

variable "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

variable "ecs_execution_role_arn" {
  description = "ARN of the ECS execution role"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
