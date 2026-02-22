# Variables for Timestream module

variable "database_name" {
  description = "Name of the Timestream database"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
