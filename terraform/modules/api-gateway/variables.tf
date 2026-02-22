# Variables for API Gateway module

variable "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
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

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for WebSocket connections"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
