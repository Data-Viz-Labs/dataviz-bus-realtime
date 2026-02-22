# Variables for Madrid Bus Real-Time Simulator Terraform configuration

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-west-1"
}

variable "timestream_database_name" {
  description = "Name of the Timestream database"
  type        = string
  default     = "bus_simulator"
}

variable "create_vpc" {
  description = "Whether to create a new VPC or use existing"
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "CIDR block for VPC if creating new"
  type        = string
  default     = "10.0.0.0/16"
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "Madrid-Bus-Simulator"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}
