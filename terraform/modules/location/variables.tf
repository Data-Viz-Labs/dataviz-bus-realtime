# Variables for Amazon Location module

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
