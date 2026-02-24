# Variables for Supporting resources module

variable "create_vpc" {
  description = "Whether to create a new VPC"
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "enable_vpc_endpoints" {
  description = "Whether to create VPC endpoints for private communication with AWS services (Secrets Manager, Timestream, CloudWatch Logs)"
  type        = bool
  default     = true
}

